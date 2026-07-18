"""
Loads the JSON documents in data/seed/ into the `documents` table with
embeddings. Each "section" in a seed file becomes one chunk/row — these
pages are already broken into small, self-contained Q&A / benefit
entries, so section-level chunking is more meaningful here than a fixed
token-window split would be.

Run with:  python -m scraper.ingest
"""
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))  # so `app` imports work

from app import db, rag

SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "seed"


def main():
    db.init_db()
    db.clear_documents()

    total = 0
    for path in sorted(SEED_DIR.glob("*.json")):
        doc = json.loads(path.read_text())
        for section in doc["sections"]:
            chunk_text = section["text"]
            embedding = rag.embed_text(f"{section['heading']}\n{chunk_text}")
            db.insert_document(
                source_url=doc["source_url"],
                title=doc["title"],
                heading=section["heading"],
                text=chunk_text,
                embedding=embedding,
            )
            total += 1
        print(f"Ingested {len(doc['sections'])} chunks from {path.name}")

    print(f"Done. {total} chunks total in `documents` table.")


if __name__ == "__main__":
    main()
