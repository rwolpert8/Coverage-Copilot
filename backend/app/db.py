"""
Database access layer.

Uses plain psycopg2 + the pgvector adapter rather than an ORM — for a
project this size an ORM would add indirection without adding safety.
Two tables:

  documents   - the chunked, embedded source corpus (MASA FAQ/benefits/about pages)
  query_logs  - every question asked + answer + retrieval + latency + cost,
                which is what the /stats dashboard and eval harness read from.
"""
import os
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

# Load .env from backend directory
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/masa_rag")
EMBEDDING_DIM = 384


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        # Try to register vector type, but don't fail if extension doesn't exist yet
        try:
            register_vector(conn)
        except psycopg2.ProgrammingError:
            pass  # Extension will be created by init_db()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create extension + tables if they don't exist yet. Safe to call on every startup."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    heading TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embedding vector({EMBEDDING_DIM})
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS query_logs (
                    id SERIAL PRIMARY KEY,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    retrieved_doc_ids INTEGER[] NOT NULL,
                    retrieval_hit BOOLEAN NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
            # ivfflat index needs data present to build well; on a corpus this
            # small a sequential scan is actually fine, so we skip an ANN index.


def clear_documents():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE documents RESTART IDENTITY;")


def insert_document(source_url: str, title: str, heading: str, text: str, embedding):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (source_url, title, heading, text, embedding) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                (source_url, title, heading, text, embedding),
            )
            return cur.fetchone()[0]


def search_similar(embedding, top_k: int = 4):
    """Cosine-distance nearest neighbor search. Returns list of dicts."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, source_url, title, heading, text,
                       1 - (embedding <=> %s) AS similarity
                FROM documents
                ORDER BY embedding <=> %s
                LIMIT %s;
                """,
                (embedding, embedding, top_k),
            )
            return cur.fetchall()


def log_query(query: str, answer: str, retrieved_doc_ids, retrieval_hit: bool,
              latency_ms: int, input_tokens=None, output_tokens=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO query_logs
                    (query, answer, retrieved_doc_ids, retrieval_hit, latency_ms, input_tokens, output_tokens)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (query, answer, retrieved_doc_ids, retrieval_hit, latency_ms, input_tokens, output_tokens),
            )


def get_stats():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    count(*) AS total_queries,
                    coalesce(avg(latency_ms), 0) AS avg_latency_ms,
                    coalesce(sum(CASE WHEN retrieval_hit THEN 1 ELSE 0 END)::float / NULLIF(count(*), 0), 0) AS retrieval_hit_rate,
                    coalesce(sum(input_tokens), 0) AS total_input_tokens,
                    coalesce(sum(output_tokens), 0) AS total_output_tokens
                FROM query_logs;
            """)
            totals = cur.fetchone()

            cur.execute("""
                SELECT date_trunc('hour', created_at) AS bucket, count(*) AS n
                FROM query_logs
                GROUP BY 1 ORDER BY 1 DESC LIMIT 24;
            """)
            recent = cur.fetchall()

            return {"totals": totals, "recent_hourly": recent}
