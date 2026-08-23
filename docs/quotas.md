# Quotas & paliers gratuits

Le script est conçu pour **ne pas dépasser** les free tiers Google. Les chiffres ci-dessous sont indicatifs : vérifie toujours la [grille tarifaire Google Maps Platform](https://developers.google.com/maps/billing-and-pricing/pricing) et [Custom Search](https://developers.google.com/custom-search/v1/overview) au moment où tu lances le script.

## Places API (New) — Text Search

| Élément | Ordre de grandeur (free tier typique) |
|---------|----------------------------------------|
| Champs Essentials (nom, adresse, website…) | ~10 000 appels / mois |
| Champs Contact (ex. `nationalPhoneNumber`) | ~5 000 appels / mois |

Le script demande le téléphone volontairement : tu es donc borné par le **SKU Contact** (~5 000/mois) si tu inclus ce champ.

**Consommation du script** : 1 appel Places par couple `catégorie × ville` (pas de pages suivantes).  
Exemple : 3 catégories × 3 villes = **9 appels Places** par exécution complète.

## Custom Search JSON API

| Élément | Free tier typique |
|---------|-------------------|
| Requêtes / jour | **100** |

Le script peut faire **jusqu'à 2 requêtes CSE par entreprise** (contact puis email), mais s'arrête dès qu'un email est trouvé.

Plafond applicatif : `MAX_EMAILS_PAR_JOUR = 30` → au pire ~60 appels CSE si chaque lead nécessite 2 requêtes, plus les entreprises sans email (1–2 appels chacune). Reste sous les 100/jour si tu ne traites pas trop de candidats sans résultat.

## Garde-fous dans le code

1. **`MAX_EMAILS_PAR_JOUR`** — stop dès que 30 emails ont été trouvés.
2. **`processed.csv`** — ne retire pas deux fois la même entreprise (économie CSE).
3. **Arrêt sur 429 / RESOURCE_EXHAUSTED** — export partiel, pas de crash en boucle.
4. **Field mask minimal** — pas de champs Pro/Enterprise Places.

## Recommandations d'usage

- Lance **une fois par jour** plutôt qu'en boucle continue.
- Commence avec **peu de villes / catégories**, élargis ensuite.
- Surveille le dashboard Cloud Billing / quotas Custom Search.
- Si tu n'as pas besoin du téléphone, tu peux retirer `nationalPhoneNumber` du field mask pour remonter au plafond Essentials (~10k) — à faire manuellement dans `PLACES_FIELD_MASK`.
