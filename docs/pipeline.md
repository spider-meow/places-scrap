# Pipeline

## Vue d'ensemble

Le script enchaîne deux API Google **en série** : Places liste les entreprises ; Custom Search n'est appelé **que** pour les fiches sans site web, non encore présentes dans `processed.csv`.

```
pour chaque catégorie
  pour chaque ville
      Places Text Search("catégorie ville")
          → parse displayName, address, phone, websiteUri
          → ignore si websiteUri présent
          → ignore si déjà dans processed.csv
          → Custom Search ("nom" ville contact | email)
          → regex emails dans title / snippet / link
          → si email : écrire dans output/leads_*.csv
          → toujours ajouter à processed.csv
      stop si MAX_EMAILS_PAR_JOUR atteint
stop si quota HTTP 429 / RESOURCE_EXHAUSTED
```

## Étape 1 — Places Text Search (API New)

- **Endpoint** : `POST https://places.googleapis.com/v1/places:searchText`
- **Headers** : `X-Goog-Api-Key`, `X-Goog-FieldMask`
- **Body** : `textQuery`, `pageSize`, `languageCode=fr`, `regionCode=FR`
- Une requête par couple catégorie × ville (pas de pagination multi-page pour limiter la consommation).

## Étape 2 — Filtre sans site

Seules les places avec `websiteUri` vide / absent sont retenues. C'est le critère métier principal (« entreprises locales sans site web »).

## Étape 3 — Custom Search + regex email

Pour chaque candidat :

1. Requête `"{nom}" {ville} contact`
2. Si aucun email : `"{nom}" {ville} email`
3. Extraction via regex sur titre, snippet, htmlSnippet et lien
4. Filtrage des faux positifs (domaines blacklistés, extensions image, etc.)
5. Conservation du **premier** email valide (qualité > volume)

Dès qu'un email est trouvé sur la première requête, la seconde n'est pas lancée.

## Étape 4 — Suivi & export

- **`processed.csv`** : clé `nom|adresse` (normalisée). Une entreprise est marquée traitée **même sans email**, pour ne pas reburner le quota CSE le lendemain.
- **`output/leads_YYYY-MM-DD.csv`** : append des leads trouvés dans la run courante.

Colonnes export :

| Colonne | Contenu |
|---------|---------|
| `nom` | displayName Places |
| `adresse` | formattedAddress |
| `telephone` | nationalPhoneNumber (peut être vide) |
| `email` | premier email public trouvé |
| `categorie` | catégorie de la boucle |
| `ville` | ville de la boucle |
| `date_extraction` | date ISO du jour |

## Gestion des erreurs

| Situation | Comportement |
|-----------|--------------|
| HTTP 429 ou `RESOURCE_EXHAUSTED` | `QuotaExceededError` → arrêt propre + export partiel |
| Autre erreur HTTP Places / CSE | log console, continue sur le prochain item |
| Clés `.env` manquantes | exit code 1 avant tout appel API |
