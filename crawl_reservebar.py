#!/usr/bin/env python3
"""
Crawl un site (par défaut us.louisxiii-cognac.com) et cherche les mentions
"ReserveBar" : texte visible, liens (<a>), iframes, scripts et HTML brut.

Usage:
    python crawl_reservebar.py
    python crawl_reservebar.py --start https://us.louisxiii-cognac.com/ --max-pages 500 --out hits.csv

Dépendances: pip install -r requirements.txt
"""

import argparse
import csv
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TARGET = re.compile(r"reserve\s*bar", re.IGNORECASE)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ReserveBarAudit/1.0)"}
SKIP_EXT = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".pdf", ".zip",
    ".mp4", ".webm", ".mp3", ".css", ".js", ".woff", ".woff2", ".ttf", ".xml",
)
CONTEXT = 80  # caractères de contexte autour de chaque occurrence


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    retry = Retry(total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def normalize(url: str) -> str:
    """Retire fragment, query de tracking et slash final pour dédupliquer."""
    p = urlparse(url)
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", p.query, ""))


def host_key(netloc: str) -> str:
    return netloc.lower().removeprefix("www.")


def is_internal(url: str, domain: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and host_key(p.netloc) == domain


def sitemap_urls(session: requests.Session, start: str, domain: str) -> list[str]:
    """Récupère les URLs du sitemap (et des sous-sitemaps) pour amorcer le crawl."""
    urls, todo, done = [], [urljoin(start, "/sitemap.xml")], set()
    while todo and len(done) < 50:
        sm = todo.pop()
        if sm in done:
            continue
        done.add(sm)
        try:
            r = session.get(sm, timeout=10)
            root = ET.fromstring(r.content)
        except (requests.RequestException, ET.ParseError):
            continue
        for loc in root.iter("{*}loc"):
            u = (loc.text or "").strip()
            if u.endswith(".xml"):
                todo.append(u)
            elif is_internal(u, domain):
                urls.append(u)
    return urls


def snippets(text: str) -> list[str]:
    out = []
    for m in TARGET.finditer(text):
        a, b = max(0, m.start() - CONTEXT), min(len(text), m.end() + CONTEXT)
        out.append(" ".join(text[a:b].split()))
    return out


def analyse(url: str, html: str) -> list[dict]:
    """Retourne une ligne par occurrence trouvée, avec son type et son contexte."""
    rows = []
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        href, label = a["href"], a.get_text(" ", strip=True)
        if TARGET.search(href) or TARGET.search(label):
            rows.append({"page": url, "kind": "link", "target": urljoin(url, href), "context": label})
    for tag in soup.find_all(["iframe", "script", "img", "form"]):
        src = tag.get("src") or tag.get("action") or ""
        if TARGET.search(src):
            rows.append({"page": url, "kind": tag.name, "target": urljoin(url, src), "context": ""})

    visible = soup.get_text(" ", strip=True)
    for s in snippets(visible):
        rows.append({"page": url, "kind": "text", "target": "", "context": s})

    # Occurrences restantes (JSON embarqué, attributs data-*, scripts inline...)
    raw_count = len(TARGET.findall(html))
    if raw_count > len(rows):
        for s in snippets(html)[: raw_count - len(rows)]:
            rows.append({"page": url, "kind": "html", "target": "", "context": s})
    return rows


def crawl(start: str, max_pages: int, delay: float, use_sitemap: bool) -> tuple[int, list[dict]]:
    session = make_session()
    domain = host_key(urlparse(start).netloc)

    queue = deque([start])
    if use_sitemap:
        seeds = sitemap_urls(session, start, domain)
        print(f"[SITEMAP] {len(seeds)} URL(s) trouvée(s)")
        queue.extend(seeds)

    queued = {normalize(u) for u in queue}
    seen: set[str] = set()
    hits: list[dict] = []

    while queue and len(seen) < max_pages:
        url = normalize(queue.popleft())
        if url in seen:
            continue
        seen.add(url)

        try:
            resp = session.get(url, timeout=15)
        except requests.RequestException as e:
            print(f"[ERREUR] {url} -> {e}")
            continue
        if resp.status_code >= 400:
            print(f"[HTTP {resp.status_code}] {url}")
            continue
        if "text/html" not in resp.headers.get("Content-Type", "").lower():
            continue

        page_url = normalize(resp.url)  # suit les redirections
        seen.add(page_url)
        html = resp.text

        rows = analyse(page_url, html)
        if rows:
            hits.extend(rows)
            print(f"[MATCH] {page_url} — {len(rows)} occurrence(s)")
        else:
            print(f"[OK] {page_url}")

        for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            link = normalize(urljoin(page_url, a["href"]))
            if (
                is_internal(link, domain)
                and link not in queued
                and not urlparse(link).path.lower().endswith(SKIP_EXT)
            ):
                queued.add(link)
                queue.append(link)

        time.sleep(delay)

    return len(seen), hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="https://us.louisxiii-cognac.com/")
    ap.add_argument("--max-pages", type=int, default=300)
    ap.add_argument("--delay", type=float, default=0.5, help="secondes entre requêtes")
    ap.add_argument("--no-sitemap", action="store_true", help="ne pas amorcer via sitemap.xml")
    ap.add_argument("--out", default="reservebar_hits.csv", help="fichier CSV de sortie")
    args = ap.parse_args()

    crawled, hits = crawl(args.start, args.max_pages, args.delay, not args.no_sitemap)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["page", "kind", "target", "context"])
        w.writeheader()
        w.writerows(hits)

    pages = sorted({h["page"] for h in hits})
    links = sorted({h["target"] for h in hits if h["target"]})
    print("\n--- Résumé ---")
    print(f"Pages crawlées : {crawled}")
    print(f"Pages avec 'ReserveBar' : {len(pages)} ({len(hits)} occurrence(s))")
    for p in pages:
        print(f"  - {p} ({sum(h['page'] == p for h in hits)})")
    if links:
        print("Liens / ressources ReserveBar :")
        for l in links:
            print(f"  -> {l}")
    print(f"Détail : {args.out}")

    if crawled <= 1 and not hits:
        print("\n[ATTENTION] Une seule page traitée : vérifie l'accès réseau au site.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
