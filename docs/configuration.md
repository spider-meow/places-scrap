# Configuration

## 1. Google Cloud — Places API (New)

1. Ouvre [Google Cloud Console](https://console.cloud.google.com/).
2. Crée un projet (ou sélectionne-en un existant).
3. Active **Places API (New)** (*Places API*).
4. Crée une clé API (APIs & Services → Credentials).
5. (Recommandé) Restreins la clé à Places API + Custom Search API, et éventuellement à ton IP.

Place la clé dans `.env` :

```env
GOOGLE_PLACES_API_KEY=...
```

### Field mask utilisé par le script

Le script n'appelle que des champs **essentiels** pour rester sur le tier gratuit :

- `places.displayName`
- `places.formattedAddress`
- `places.nationalPhoneNumber` (SKU Contact — quota gratuit plus bas)
- `places.websiteUri`

Aucun champ Pro / Enterprise n'est demandé.

## 2. Google Custom Search JSON API

1. Dans le même projet Cloud (ou un autre), active **Custom Search API**.
2. Crée / réutilise une clé API → `GOOGLE_CSE_API_KEY`.
3. Crée un moteur sur [Programmable Search Engine](https://programmablesearchengine.google.com/) :
   - Coche **Rechercher sur tout le web**.
   - Récupère l'identifiant **cx** → `GOOGLE_CSE_CX`.

```env
GOOGLE_CSE_API_KEY=...
GOOGLE_CSE_CX=...
```

Tu peux utiliser **la même clé Cloud** pour Places et CSE si les deux APIs sont activées sur le projet ; le script attend quand même deux variables distinctes pour plus de clarté.

## 3. Fichier `.env`

```bash
cp .env.example .env
```

Exemple :

```env
GOOGLE_PLACES_API_KEY=AIza...
GOOGLE_CSE_API_KEY=AIza...
GOOGLE_CSE_CX=a1b2c3d4e5f6g7h8i
```

Le fichier `.env` est dans `.gitignore` — ne le pousse jamais sur GitHub.

## 4. Paramètres dans le script

Éditables en haut de `find_leads.py` :

| Variable | Défaut | Rôle |
|----------|--------|------|
| `CATEGORIES` | coiffeur, restaurant, plombier | Types d'activité Places |
| `VILLES` | Rueil-Malmaison, Nanterre, Suresnes | Zones géographiques |
| `MAX_EMAILS_PAR_JOUR` | 30 | Plafond d'emails trouvés / run (qualité) |
| `PLACES_PAGE_SIZE` | 20 | Max résultats par requête Places (1–20) |

## 5. Vérification rapide

```bash
python find_leads.py
```

Si une clé manque, le script s'arrête avec un message listant les variables absentes.
