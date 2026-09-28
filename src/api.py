"""
FastAPI backend — exposes the REST surface from the product spec (section 7.3)
so the Next.js frontend (or anything else) can talk to the memory system
over plain HTTP instead of importing Python modules directly.

Run with: uvicorn src.api:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from src.graph_store import GraphStore
from src.vector_store import VectorStore
from src.agent import build_agent
from src.retrieval import retrieve
from src.models import MemoryFact, MemoryType, PolicyClass

app = FastAPI(title="Spotify Memory System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only — restrict this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = GraphStore()
vectors = VectorStore()
agent = build_agent(graph, vectors)


# ---------- request/response schemas ----------

class ChatRequest(BaseModel):
    subject_id: str
    message: str


class ChatResponse(BaseModel):
    response: str


class ExplicitPreferenceRequest(BaseModel):
    subject_id: str
    fact_text: str
    entities: list[str] = []


class CorrectionRequest(BaseModel):
    subject_id: str
    corrected_fact_text: str
    entities: list[str] = []


# ---------- endpoints ----------

@app.post("/v1/events", response_model=ChatResponse)
def send_message(req: ChatRequest):
    """Send a chat turn. Runs capture -> retrieve -> generate and returns the reply."""
    result = agent.invoke({"subject_id": req.subject_id, "user_message": req.message})
    return ChatResponse(response=result["response"])


@app.get("/v1/memories")
def list_memories(subject_id: str):
    """List active memories for a subject (Memory Console timeline)."""
    return graph.get_active_memories(subject_id)


@app.post("/v1/memories/search")
def search_memories(subject_id: str, intent: str):
    """Ranked retrieval for a given intent (Context preview panel)."""
    results = retrieve(subject_id, intent, graph, vectors)
    return [
        {
            "memory_id": r.memory.memory_id,
            "fact_text": r.memory.fact_text,
            "memory_type": r.memory.memory_type.value,
            "confidence": r.memory.confidence,
            "relevance_score": r.relevance_score,
            "relevance_reason": r.relevance_reason,
        }
        for r in results
    ]


@app.post("/v1/memories/explicit")
def add_explicit_preference(req: ExplicitPreferenceRequest):
    fact = MemoryFact(
        subject_id=req.subject_id,
        memory_type=MemoryType.EXPLICIT_PREFERENCE,
        fact_text=req.fact_text,
        entities=req.entities,
        confidence=0.95,
        policy_class=PolicyClass.STANDARD,
    )
    graph.upsert_memory(fact)
    vectors.upsert(fact.memory_id, fact.subject_id, fact.fact_text)
    return {"memory_id": fact.memory_id, "status": "created"}


@app.patch("/v1/memories/{memory_id}")
def correct_memory(memory_id: str, req: CorrectionRequest):
    new_fact = MemoryFact(
        subject_id=req.subject_id,
        memory_type=MemoryType.CORRECTION,
        fact_text=req.corrected_fact_text,
        entities=req.entities,
        confidence=0.95,
        policy_class=PolicyClass.STANDARD,
    )
    graph.upsert_memory(new_fact)
    graph.supersede_memory(memory_id, new_fact.memory_id)
    vectors.upsert(new_fact.memory_id, new_fact.subject_id, new_fact.fact_text)
    return {"new_memory_id": new_fact.memory_id, "status": "superseded_old"}


@app.delete("/v1/memories/{memory_id}")
def delete_memory(memory_id: str):
    graph.delete_memory(memory_id)
    vectors.delete(memory_id)
    return {"memory_id": memory_id, "status": "deleted"}


@app.get("/v1/health")
def health():
    return {"status": "ok"}
