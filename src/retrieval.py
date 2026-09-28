"""
Hybrid retrieval: combines relational candidates from the graph with semantic
candidates from the vector index, then reranks by intent fit, explicitness,
confidence, and recency before handing results to the context composer.
"""
from datetime import datetime
from src.models import MemoryFact, MemoryType, RetrievedMemory
from src.graph_store import GraphStore
from src.vector_store import VectorStore
from src.config import settings

TYPE_WEIGHT = {
    MemoryType.EXPLICIT_PREFERENCE: 1.0,
    MemoryType.CORRECTION: 1.0,
    MemoryType.EXCLUSION: 0.9,
    MemoryType.CANDIDATE_PREFERENCE: 0.6,
    MemoryType.EPISODE: 0.3,
}


def _recency_score(valid_from: str) -> float:
    try:
        ts = datetime.fromisoformat(valid_from)
        age_days = (datetime.now(ts.tzinfo) - ts).days
        return max(0.0, 1.0 - age_days / 90.0)  # decays to 0 over ~3 months
    except Exception:
        return 0.5


def retrieve(
    subject_id: str, intent: str, graph: GraphStore, vectors: VectorStore
) -> list[RetrievedMemory]:
    graph_candidates = {m["memory_id"]: m for m in graph.get_active_memories(subject_id)}
    vector_hits = vectors.search(subject_id, intent, top_k=15)

    scored: dict[str, RetrievedMemory] = {}

    for hit in vector_hits:
        gm = graph_candidates.get(hit["memory_id"])
        if not gm or gm.get("status") != "active":
            continue
        mtype = MemoryType(gm["memory_type"])
        score = (
            0.5 * hit["score"]
            + 0.25 * gm.get("confidence", 0.5)
            + 0.15 * TYPE_WEIGHT.get(mtype, 0.3)
            + 0.10 * _recency_score(gm.get("valid_from", ""))
        )
        scored[gm["memory_id"]] = RetrievedMemory(
            memory=MemoryFact(**gm),
            relevance_score=round(score, 4),
            relevance_reason=f"semantic match ({hit['score']:.2f}) + {mtype.value}",
        )

    # Always surface high-confidence explicit preferences/exclusions even if the
    # vector search didn't rank them top-15 for this particular intent phrasing.
    for gm in graph_candidates.values():
        if gm["memory_id"] in scored:
            continue
        mtype = MemoryType(gm["memory_type"])
        if mtype in (MemoryType.EXPLICIT_PREFERENCE, MemoryType.EXCLUSION) and gm.get(
            "confidence", 0
        ) >= 0.8:
            scored[gm["memory_id"]] = RetrievedMemory(
                memory=MemoryFact(**gm),
                relevance_score=0.7,
                relevance_reason="high-confidence explicit fact (relational recall)",
            )

    ranked = sorted(scored.values(), key=lambda r: r.relevance_score, reverse=True)
    return ranked[: settings.MAX_CONTEXT_MEMORIES]
