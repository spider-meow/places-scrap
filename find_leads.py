"""
Script : trouver des entreprises locales sans site web et récupérer un email public.

Pipeline :
1. Google Places API (New) — Text Search → entreprises par catégorie × ville
2. Filtrer celles sans websiteUri
3. Google Custom Search JSON → chercher un email public dans les snippets
4. Exporter en CSV (plafond 30 emails/jour + dédup entre exécutions)
"""

from __future__ import annotations

import csv
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# =============================================================================
# CONFIGURATION — à adapter selon tes besoins
# =============================================================================

# Catégories d'activité à rechercher (requête Places Text Search)
CATEGORIES: list[str] = ["coiffeur", "restaurant", "plombier"]

# Villes cibles
VILLES: list[str] = ["Rueil-Malmaison", "Nanterre", "Suresnes"]

# Plafond d'emails trouvés par jour (ne jamais dépasser le free tier Custom Search)
MAX_EMAILS_PAR_JOUR = 30

# Nombre max de résultats Places par requête (1–20 ; 20 = max par page)
PLACES_PAGE_SIZE = 20

# Fichiers locaux
PROCESSED_FILE = Path("processed.csv")
OUTPUT_DIR = Path("output")

# =============================================================================
# CHARGEMENT DES CLÉS API (.env) — jamais en dur dans le code
# =============================================================================

load_dotenv()

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
GOOGLE_CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY", "").strip()
GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX", "").strip()  # ID du moteur Programmable Search

# Endpoints officiels Google
PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# Field mask Places : champs essentiels uniquement (tier gratuit)
# nationalPhoneNumber = SKU Contact (5 000 gratuits/mois) — volontairement inclus
PLACES_FIELD_MASK = (
    "places.displayName,places.formattedAddress,"
    "places.nationalPhoneNumber,places.websiteUri"
)

# Regex email (simple, adaptée aux snippets de résultats de recherche)
EMAIL_REGEX = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
)

# Domaines à ignorer (souvent non pertinents pour un contact pro local)
EMAIL_BLACKLIST_DOMAINS = {
    "sentry.io",
    "example.com",
    "email.com",
    "domain.com",
    "wixpress.com",
    "googleapis.com",
    "schema.org",
    "google.com",
    "gstatic.com",
}


# =============================================================================
# EXCEPTIONS MÉTIER
# =============================================================================


class QuotaExceededError(Exception):
    """Levée quand une API renvoie 429 / RESOURCE_EXHAUSTED — arrêt propre."""


# =============================================================================
# UTILITAIRES : clé unique, CSV, validation email
# =============================================================================


def make_key(nom: str, adresse: str) -> str:
    """Clé unique pour dédupliquer (nom + adresse, normalisés)."""
    return f"{nom.strip().lower()}|{adresse.strip().lower()}"


def is_valid_email(email: str) -> bool:
    """Filtre les faux positifs courants dans les snippets Google."""
    email = email.strip().lower()
    if email.count("@") != 1:
        return False
    local, domain = email.split("@", 1)
    if not local or not domain or "." not in domain:
        return False
    # Extensions d'images / fichiers souvent capturées par erreur
    if domain.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")):
        return False
    if any(domain == bl or domain.endswith("." + bl) for bl in EMAIL_BLACKLIST_DOMAINS):
        return False
    return True


def extract_emails_from_text(text: str) -> list[str]:
    """Extrait et déduplique les emails valides trouvés dans un texte."""
    found: list[str] = []
    seen: set[str] = set()
    for match in EMAIL_REGEX.findall(text or ""):
        email = match.lower()
        if email not in seen and is_valid_email(email):
            seen.add(email)
            found.append(email)
    return found


def load_processed_keys(path: Path) -> set[str]:
    """Charge les entreprises déjà traitées depuis processed.csv."""
    if not path.exists():
        return set()
    keys: set[str] = set()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nom = row.get("nom", "")
            adresse = row.get("adresse", "")
            if nom or adresse:
                keys.add(make_key(nom, adresse))
    return keys


def append_processed(path: Path, nom: str, adresse: str, date_str: str) -> None:
    """Ajoute une entreprise au fichier de suivi (création avec en-tête si besoin)."""
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["nom", "adresse", "date_traitement"])
        if write_header:
            writer.writeheader()
        writer.writerow(
            {"nom": nom, "adresse": adresse, "date_traitement": date_str}
        )


def write_daily_results(rows: list[dict[str, str]], output_dir: Path, day: date) -> Path:
    """Exporte les résultats du jour dans output/leads_YYYY-MM-DD.csv."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"leads_{day.isoformat()}.csv"
    fieldnames = [
        "nom",
        "adresse",
        "telephone",
        "email",
        "categorie",
        "ville",
        "date_extraction",
    ]
    # Append si le fichier du jour existe déjà (plusieurs runs le même jour)
    write_header = not out_path.exists()
    with out_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return out_path


def check_quota_response(response: requests.Response, api_name: str) -> None:
    """Détecte les erreurs de quota et lève QuotaExceededError pour arrêt propre."""
    if response.status_code == 429:
        raise QuotaExceededError(f"Quota dépassé ({api_name}) — HTTP 429.")

    # Places / Google API : parfois 403 avec status RESOURCE_EXHAUSTED
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    status = str(error.get("status", "")).upper()
    message = str(error.get("message", "")).lower()

    if status in {"RESOURCE_EXHAUSTED", "PERMISSION_DENIED"} and (
        "quota" in message or "rate" in message or "exhausted" in message
    ):
        raise QuotaExceededError(
            f"Quota dépassé ({api_name}) — {status}: {error.get('message', '')}"
        )


# =============================================================================
# ÉTAPE 1 — Google Places API (New) : Text Search
# =============================================================================


def places_text_search(query: str, api_key: str) -> list[dict[str, Any]]:
    """
    Interroge Places Text Search (endpoint New) pour une requête donnée.
    Ne demande que les champs essentiels (field mask) pour rester sur le tier gratuit.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": PLACES_FIELD_MASK,
    }
    body = {
        "textQuery": query,
        "pageSize": PLACES_PAGE_SIZE,
        "languageCode": "fr",
        "regionCode": "FR",
    }

    response = requests.post(
        PLACES_TEXT_SEARCH_URL, headers=headers, json=body, timeout=30
    )
    check_quota_response(response, "Places API")

    if not response.ok:
        # Autre erreur HTTP : on log et on renvoie une liste vide (pas de crash)
        print(
            f"  [Places] Erreur HTTP {response.status_code} pour « {query} » : "
            f"{response.text[:200]}"
        )
        return []

    data = response.json()
    return data.get("places", [])


def parse_place(place: dict[str, Any]) -> dict[str, str]:
    """Normalise un objet Place en dict simple."""
    display = place.get("displayName") or {}
    nom = display.get("text", "") if isinstance(display, dict) else str(display)
    return {
        "nom": nom.strip(),
        "adresse": (place.get("formattedAddress") or "").strip(),
        "telephone": (place.get("nationalPhoneNumber") or "").strip(),
        "website": (place.get("websiteUri") or "").strip(),
    }


# =============================================================================
# ÉTAPE 2 — Filtre : entreprises sans site web
# =============================================================================


def sans_site_web(place_parsed: dict[str, str]) -> bool:
    """True si websiteUri est absent / vide."""
    return not place_parsed.get("website")


# =============================================================================
# ÉTAPE 3 — Google Custom Search JSON : email public dans les snippets
# =============================================================================


def custom_search_emails(
    nom: str, ville: str, api_key: str, cx: str
) -> list[str]:
    """
    Cherche un email public via Custom Search (2 requêtes max par entreprise).
    Extrait les emails des titres / snippets / liens affichés.
    """
    queries = [
        f'"{nom}" {ville} contact',
        f'"{nom}" {ville} email',
    ]
    collected: list[str] = []
    seen: set[str] = set()

    for q in queries:
        params = {
            "key": api_key,
            "cx": cx,
            "q": q,
            "num": 5,  # peu de résultats : qualité > volume, économise le quota
            "hl": "fr",
            "gl": "fr",
        }
        response = requests.get(CUSTOM_SEARCH_URL, params=params, timeout=30)
        check_quota_response(response, "Custom Search API")

        if not response.ok:
            print(
                f"  [CSE] Erreur HTTP {response.status_code} pour « {q} » : "
                f"{response.text[:200]}"
            )
            continue

        data = response.json()
        for item in data.get("items", []):
            blob = " ".join(
                [
                    item.get("title", ""),
                    item.get("snippet", ""),
                    item.get("htmlSnippet", ""),
                    item.get("link", ""),
                ]
            )
            for email in extract_emails_from_text(blob):
                if email not in seen:
                    seen.add(email)
                    collected.append(email)

        # Dès qu'on a au moins un email, on arrête (qualité, pas volume)
        if collected:
            break

    return collected


# =============================================================================
# PIPELINE PRINCIPAL
# =============================================================================


def validate_env() -> None:
    """Vérifie que les clés nécessaires sont présentes avant de démarrer."""
    missing = []
    if not GOOGLE_PLACES_API_KEY:
        missing.append("GOOGLE_PLACES_API_KEY")
    if not GOOGLE_CSE_API_KEY:
        missing.append("GOOGLE_CSE_API_KEY")
    if not GOOGLE_CSE_CX:
        missing.append("GOOGLE_CSE_CX")
    if missing:
        print(
            "Clés manquantes dans .env : "
            + ", ".join(missing)
            + "\nCopie .env.example vers .env et renseigne tes clés."
        )
        sys.exit(1)


def main() -> None:
    validate_env()

    today = date.today()
    today_str = today.isoformat()
    processed = load_processed_keys(PROCESSED_FILE)
    results: list[dict[str, str]] = []
    emails_trouves = 0

    print(f"=== Extraction du {today_str} ===")
    print(f"Catégories : {CATEGORIES}")
    print(f"Villes     : {VILLES}")
    print(f"Plafond    : {MAX_EMAILS_PAR_JOUR} emails / jour")
    print(f"Déjà traités (processed.csv) : {len(processed)}")
    print()

    try:
        for categorie in CATEGORIES:
            for ville in VILLES:
                if emails_trouves >= MAX_EMAILS_PAR_JOUR:
                    break

                query = f"{categorie} {ville}"
                print(f"[Places] Recherche : {query}")
                places = places_text_search(query, GOOGLE_PLACES_API_KEY)
                print(f"  → {len(places)} résultat(s)")

                for place in places:
                    if emails_trouves >= MAX_EMAILS_PAR_JOUR:
                        print(
                            f"\nPlafond atteint ({MAX_EMAILS_PAR_JOUR} emails). Arrêt."
                        )
                        break

                    parsed = parse_place(place)
                    nom = parsed["nom"]
                    adresse = parsed["adresse"]

                    if not nom:
                        continue

                    # Filtre : uniquement sans site web
                    if not sans_site_web(parsed):
                        continue

                    key = make_key(nom, adresse)
                    if key in processed:
                        continue

                    print(f"  [Sans site] {nom} — {adresse}")
                    print("    → Custom Search…")

                    emails = custom_search_emails(
                        nom, ville, GOOGLE_CSE_API_KEY, GOOGLE_CSE_CX
                    )

                    # Marquer comme traité même sans email (évite de reconsommer le quota CSE)
                    append_processed(PROCESSED_FILE, nom, adresse, today_str)
                    processed.add(key)

                    if not emails:
                        print("    → aucun email public trouvé")
                        continue

                    # On garde le premier email valide (qualité > volume)
                    email = emails[0]
                    emails_trouves += 1
                    print(f"    → email : {email} ({emails_trouves}/{MAX_EMAILS_PAR_JOUR})")

                    results.append(
                        {
                            "nom": nom,
                            "adresse": adresse,
                            "telephone": parsed["telephone"],
                            "email": email,
                            "categorie": categorie,
                            "ville": ville,
                            "date_extraction": today_str,
                        }
                    )

            if emails_trouves >= MAX_EMAILS_PAR_JOUR:
                break

    except QuotaExceededError as exc:
        print(f"\n[STOP] {exc}")
        print("Export partiel des résultats déjà collectés…")

    # Export CSV du jour
    if results:
        out_path = write_daily_results(results, OUTPUT_DIR, today)
        print(f"\n{len(results)} lead(s) exporté(s) → {out_path}")
    else:
        print("\nAucun nouvel email trouvé pour cette exécution.")

    print(f"Total emails trouvés aujourd'hui (cette run) : {emails_trouves}")
    print("Terminé.")


if __name__ == "__main__":
    main()
