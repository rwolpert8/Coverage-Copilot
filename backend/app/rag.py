"""
Core RAG logic: embed -> retrieve -> generate.

Embeddings run locally via fastembed (ONNX, no API key, small enough to
run on a free-tier deploy). Generation calls the Anthropic API. Keeping
these as separate, swappable steps is what makes the /eval harness and
/stats logging possible in the first place.
"""
import os
from fastembed import TextEmbedding
from anthropic import Anthropic

from . import db

_embedder = None
_anthropic_client = None

SYSTEM_PROMPT = """You are a support assistant for MASA (Medical Access & Service Advantage), \
a company that provides emergency medical transportation benefit memberships.

Answer the member's question using ONLY the context provided below. If the context doesn't \
contain enough information to answer confidently, say so plainly and suggest they contact \
MASA Member Services rather than guessing.

Keep answers concise (2-5 sentences). Do not invent benefit amounts, plan names, or coverage \
details that are not present in the context.

Context:
{context}
"""


def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        # bge-small-en-v1.5 -> 384-dim, matches EMBEDDING_DIM in db.py
        _embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _embedder


def get_anthropic_client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _anthropic_client


def embed_text(text: str):
    embedder = get_embedder()
    return list(embedder.embed([text]))[0]  # Keep as numpy array for pgvector


# Similarity below this is treated as "didn't really find anything relevant" -
# feeds the retrieval_hit_rate metric on the /stats dashboard.
RELEVANCE_THRESHOLD = 0.35


def answer_question(query: str, top_k: int = 4):
    query_embedding = embed_text(query)
    matches = db.search_similar(query_embedding, top_k=top_k)

    retrieval_hit = bool(matches) and matches[0]["similarity"] >= RELEVANCE_THRESHOLD

    if not matches or not retrieval_hit:
        context = "(no sufficiently relevant context found in the knowledge base)"
    else:
        context = "\n\n".join(
            f"[{m['heading']}] (source: {m['source_url']})\n{m['text']}" for m in matches
        )

    client = get_anthropic_client()
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=400,
        system=SYSTEM_PROMPT.format(context=context),
        messages=[{"role": "user", "content": query}],
    )
    answer_text = "".join(block.text for block in message.content if block.type == "text")

    return {
        "answer": answer_text,
        "sources": [
            {"heading": m["heading"], "source_url": m["source_url"], "similarity": round(m["similarity"], 3)}
            for m in matches
        ],
        "retrieval_hit": retrieval_hit,
        "retrieved_doc_ids": [m["id"] for m in matches],
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }
