"""
Scrapes MASA's public pages into the same JSON shape used in data/seed/,
so the corpus can be refreshed or extended later.

The data/seed/*.json files already checked into this repo were built by
hand from these same pages as a starting corpus (fetched at the time this
project was built) — run this script yourself to pull the current live
version, or point it at additional pages, e.g. individual
/benefits/<slug>/ detail pages for more granular chunks.

Run with:  python -m scraper.scrape_masa
"""
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "seed"

# Add more URLs here (e.g. individual benefit detail pages) to grow the corpus.
PAGES = [
    ("https://masaaccess.com/what-is-masa/", "about_scraped.json"),
    ("https://masaaccess.com/faq/", "faq_scraped.json"),
    ("https://masaaccess.com/benefits/", "benefits_scraped.json"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0; personal-project)"}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_sections(soup: BeautifulSoup):
    """
    Naive but effective for HubSpot-style pages: treat each h2 (or h3 if no
    h2 is present) as a section heading, and grab the text of sibling
    elements until the next heading of the same level.
    """
    sections = []
    headings = soup.find_all(["h2", "h3"])
    for i, h in enumerate(headings):
        heading_text = clean(h.get_text())
        if not heading_text or len(heading_text) < 3:
            continue
        body_parts = []
        for sib in h.find_next_siblings():
            if sib.name in ("h2", "h3"):
                break
            text = clean(sib.get_text())
            if text:
                body_parts.append(text)
        body = " ".join(body_parts).strip()
        if body:
            sections.append({"heading": heading_text, "text": body})
    return sections


def scrape_page(url: str):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.find("title")
    title = clean(title_tag.get_text()) if title_tag else url

    # Drop nav/footer noise before extracting sections
    for tag in soup.select("nav, footer, header, script, style"):
        tag.decompose()

    sections = extract_sections(soup)
    return {"source_url": url, "title": title, "sections": sections}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for url, filename in PAGES:
        print(f"Scraping {url} ...")
        doc = scrape_page(url)
        out_path = OUT_DIR / filename
        out_path.write_text(json.dumps(doc, indent=2))
        print(f"  -> {len(doc['sections'])} sections written to {out_path}")
        time.sleep(1)  # be polite


if __name__ == "__main__":
    main()
