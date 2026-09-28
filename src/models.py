"""
Typed contracts for the memory system: interaction events, candidate memories,
graph facts, and the context package handed to the LLM.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from uuid import uuid4
from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryType(str, Enum):
    EPISODE = "episode"                    # transient interaction, low durability
    EXPLICIT_PREFERENCE = "explicit_preference"  # user stated it directly
    CANDIDATE_PREFERENCE = "candidate_preference"  # inferred, needs more evidence
    EXCLUSION = "exclusion"                # "don't recommend X"
    CORRECTION = "correction"              # supersedes a prior fact


class PolicyClass(str, Enum):
    STANDARD = "standard"
    SENSITIVE = "sensitive"       # e.g. inferred mood/emotional state
    BLOCKED = "blocked"           # never persisted


class InteractionEvent(BaseModel):
    """A raw event entering the system (a chat turn, a skip, a save, etc.)."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    subject_id: str                     # the user
    surface: str                        # e.g. "chat", "playlist", "podcast"
    event_type: str                     # e.g. "message", "skip", "save", "explicit_statement"
    text: Optional[str] = None
    locale: str = "en-IN"
    timestamp: str = Field(default_factory=now_iso)
    idempotency_key: str = Field(default_factory=lambda: str(uuid4()))


class MemoryFact(BaseModel):
    """A single memory as stored in the graph + vector index."""
    memory_id: str = Field(default_factory=lambda: str(uuid4()))
    subject_id: str
    memory_type: MemoryType
    fact_text: str                      # normalized natural-language fact
    entities: List[str] = Field(default_factory=list)
    confidence: float = 0.5             # 0..1
    policy_class: PolicyClass = PolicyClass.STANDARD
    source_event_id: Optional[str] = None
    valid_from: str = Field(default_factory=now_iso)
    valid_to: Optional[str] = None      # set when superseded/expired
    status: str = "active"              # active | superseded | expired | deleted
    superseded_by: Optional[str] = None


class RetrievedMemory(BaseModel):
    memory: MemoryFact
    relevance_score: float
    relevance_reason: str


class ContextPackage(BaseModel):
    subject_id: str
    intent: str
    memories: List[RetrievedMemory]
    fallback: bool = False              # True => no-memory fallback was used
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
