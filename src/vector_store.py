"""
Embedding + vector index layer. Every vector is stored under the same
memory_id used in the graph so updates/deletes stay aligned across stores.
"""
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import SentenceTransformer
from src.config import settings

_embedder: Optional[SentenceTransformer] = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embedder


class VectorStore:
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self._ensure_collection()

    def _ensure_collection(self):
        collections = [c.name for c in self.client.get_collections().collections]
        if settings.QDRANT_COLLECTION not in collections:
            self.client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=qmodels.VectorParams(
                    size=settings.EMBEDDING_DIM, distance=qmodels.Distance.COSINE
                ),
            )

    def upsert(self, memory_id: str, subject_id: str, text: str) -> None:
        vector = get_embedder().encode(text).tolist()
        self.client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=[
                qmodels.PointStruct(
                    id=memory_id,
                    vector=vector,
                    payload={"subject_id": subject_id, "fact_text": text},
                )
            ],
        )

    def search(self, subject_id: str, query: str, top_k: int = 10) -> List[dict]:
        vector = get_embedder().encode(query).tolist()
        results = self.client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=vector,
            query_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="subject_id", match=qmodels.MatchValue(value=subject_id)
                    )
                ]
            ),
            limit=top_k,
        )
        return [
            {"memory_id": r.id, "score": r.score, **(r.payload or {})} for r in results
        ]

    def delete(self, memory_id: str) -> None:
        self.client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=qmodels.PointIdsList(points=[memory_id]),
        )
