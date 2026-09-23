#!/usr/bin/env python3
"""
Crawl us.louisxiii-cognac.com et cherche les mentions "ReserveBar" (texte + liens).
Usage: python crawl_reservebar.py
Dépendances: pip install requests beautifulsoup4
"""

import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

START_URL = "https://us.louisxiii-cognac.com/"
DOMAIN = urlparse(START_URL).netloc
MAX_PAGES = 300          # limite de sécurité
DELAY = 0.5              # secondes entre requêtes, pour rester poli
TARGET = re.compile(r"reservebar", re.IGNORECASE)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ReserveBarAudit/1.0)"}


def is_internal(url: str) -> bool:
    return urlparse(url).netloc in ("", DOMAIN)


def normalize(url: str) -> str:
    url = url.split("#")[0]
    if url.endswith("/") and url != START_URL:
        url = url[:-1]
    return url


def crawl():
    seen = set()
    queue = deque([START_URL])
    hits = []

    while queue and len(seen) < MAX_PAGES:
        url = queue.popleft()
        url = normalize(url)
        if url in seen:
            continue
        seen.add(url)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
        except requests.RequestException as e:
            print(f"[ERREUR] {url} -> {e}")
            continue

        if "text/html" not in resp.headers.get("Content-Type", ""):
            continue

        html = resp.text
        matches = TARGET.findall(html)
        if matches:
            hits.append((url, len(matches)))
            print(f"[MATCH] {url} — {len(matches)} occurrence(s)")

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            link = normalize(link)
            if is_internal(link) and link not in seen and link.startswith("http"):
                queue.append(link)

        time.sleep(DELAY)

    print("\n--- Résumé ---")
    print(f"Pages crawlées : {len(seen)}")
    print(f"Pages avec 'ReserveBar' : {len(hits)}")
    for url, count in hits:
        print(f"  - {url} ({count})")

    return hits


if __name__ == "__main__":
    crawl()
