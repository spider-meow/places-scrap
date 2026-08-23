# places-scrap

Script Python pour trouver des **entreprises locales sans site web** et récupérer un **email public**, uniquement via les API officielles Google (Places + Custom Search), en restant dans les paliers gratuits.

Usage personnel, orienté **qualité plutôt que volume** (plafond journalier d’emails).

## Fonctionnalités

- Recherche Places (Text Search, API New) par **catégorie × ville**
- Filtre des fiches **sans `websiteUri`**
- Enrichissement email via **Google Custom Search JSON** (snippets + regex)
- Déduplication entre exécutions (`processed.csv`)
- Plafond **30 emails / jour** + arrêt propre sur quota (HTTP 429)
- Export CSV quotidien dans `output/`

## Prérequis

- Python 3.10+
- Un projet [Google Cloud](https://console.cloud.google.com/) avec :
  - **Places API (New)** activée
  - **Custom Search API** activée
- Un moteur [Programmable Search Engine](https://programmablesearchengine.google.com/) configuré pour **rechercher sur tout le web** (obtenir le `cx`)

## Installation

```bash
git clone https://github.com/spider-meow/places-scrap.git
cd places-scrap

python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Renseigne les clés dans `.env` (voir [docs/configuration.md](docs/configuration.md)).

## Configuration rapide

En haut de `find_leads.py` :

```python
CATEGORIES = ["coiffeur", "restaurant", "plombier"]
VILLES = ["Rueil-Malmaison", "Nanterre", "Suresnes"]
MAX_EMAILS_PAR_JOUR = 30
```

Variables d’environnement (`.env`) :

| Variable | Description |
|----------|-------------|
| `GOOGLE_PLACES_API_KEY` | Clé API Places (New) |
| `GOOGLE_CSE_API_KEY` | Clé API Custom Search |
| `GOOGLE_CSE_CX` | ID du moteur Programmable Search (`cx`) |

## Utilisation

```bash
python find_leads.py
```

Sorties :

| Fichier | Rôle |
|---------|------|
| `output/leads_YYYY-MM-DD.csv` | Leads du jour (nom, adresse, téléphone, email, catégorie, ville, date) |
| `processed.csv` | Entreprises déjà traitées (évite de reconsommer le quota CSE) |

## Pipeline

```
CATEGORIES × VILLES
        │
        ▼
 Places Text Search  ──field mask──► displayName, address, phone, websiteUri
        │
        ▼
 Filtre : websiteUri absent
        │
        ▼
 Custom Search (« nom + ville + contact/email »)
        │
        ▼
 Regex email dans les snippets
        │
        ▼
 CSV + processed.csv  (stop à 30 emails ou quota API)
```

Détails : [docs/pipeline.md](docs/pipeline.md) · Quotas : [docs/quotas.md](docs/quotas.md)

## Structure du dépôt

```
places-scrap/
├── find_leads.py      # Script principal
├── .env.example       # Modèle de clés API
├── requirements.txt
├── docs/
│   ├── configuration.md
│   ├── pipeline.md
│   └── quotas.md
└── output/            # Généré à l’exécution (gitignoré)
```

## Limites & éthique

- Aucun appel téléphonique, aucun scraping Facebook/Instagram.
- Uniquement des données **publiques** déjà indexées / exposées par Google.
- Respecte les conditions d’utilisation Google et le RGPD pour tout usage des contacts récupérés.
- Ne commit jamais ton fichier `.env`.

## Licence

Usage personnel. Adapte selon tes besoins.
