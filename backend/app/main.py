import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import db
from . import rag

app = FastAPI(title="Coverage Copilot API")

# CORS: wide open for development. Tighten to your deployed frontend's
# origin before deploying to production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    db.init_db()


class AskRequest(BaseModel):
    query: str


class AskResponse(BaseModel):
    answer: str
    sources: list
    retrieval_hit: bool


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    start = time.perf_counter()
    result = rag.answer_question(req.query)
    latency_ms = int((time.perf_counter() - start) * 1000)

    db.log_query(
        query=req.query,
        answer=result["answer"],
        retrieved_doc_ids=result["retrieved_doc_ids"],
        retrieval_hit=result["retrieval_hit"],
        latency_ms=latency_ms,
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
    )

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "retrieval_hit": result["retrieval_hit"],
    }


@app.get("/stats")
def stats():
    return db.get_stats()


@app.get("/ingest")
def ingest():
    """Temporary endpoint to ingest seed data into Railway database."""
    import json
    from pathlib import Path
    
    seed_dir = Path(__file__).resolve().parents[2] / "data" / "seed"
    
    db.clear_documents()
    total = 0
    
    for path in sorted(seed_dir.glob("*.json")):
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
    
    return {"status": "success", "chunks_ingested": total}
