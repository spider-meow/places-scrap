# ReserveBar crawler

Crawl `us.louisxiii-cognac.com` (ou un autre site) et liste toutes les mentions de **ReserveBar** : liens, texte visible, iframes/scripts et HTML brut (JSON embarqué, etc.).

```bash
pip install -r requirements.txt
python crawl_reservebar.py
```

Options :

| Option | Défaut | Rôle |
|---|---|---|
| `--start` | `https://us.louisxiii-cognac.com/` | URL de départ |
| `--max-pages` | `300` | Limite de pages |
| `--delay` | `0.5` | Pause entre requêtes (s) |
| `--no-sitemap` | – | Ne pas amorcer via `sitemap.xml` |
| `--out` | `reservebar_hits.csv` | CSV détaillé (page, type, cible, contexte) |

Le script ne voit que le HTML servi par le serveur. Il ne voit pas le contenu injecté en JavaScript après le chargement de la page.
