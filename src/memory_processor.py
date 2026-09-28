"""
Extraction and entity resolution: classifies an interaction event into
zero or more typed candidate memories, using the LLM for the judgment call
and deterministic rules for policy/safety filtering.
"""
import json

from src.llm import get_llm
from src.models import InteractionEvent, MemoryFact, MemoryType, PolicyClass
from src.graph_store import GraphStore
from src.vector_store import VectorStore


EXTRACTION_SYSTEM_PROMPT = """You are a memory-extraction module for a music/podcast \
app's AI memory system. Given one user interaction, decide whether it contains a \
durable fact worth remembering.

Allowed memory types: episode, explicit_preference, candidate_preference, exclusion, correction.

Rules:
- Only extract explicit_preference when the user directly states a lasting preference \
("I always want", "I hate", "never recommend").
- Use candidate_preference for something implied but not yet confirmed.
- Use exclusion for "don't play/recommend X".
- Use correction whenever the user changes, reverses, updates, replaces, or contradicts a previous preference.
- Strong correction signals include phrases such as "I changed my mind", "now I prefer", \
"I don't want that anymore", "I no longer want", "instead", "actually", "but now", \
"I prefer X now", or "I used to prefer X".
- When a user explicitly changes a previous preference, ALWAYS use memory_type="correction", \
not candidate_preference.
- Use episode for a one-off, non-durable interaction (skip a song, a single mood mention).
- NEVER infer or store emotional/mental-health state as a durable fact. Mark such content \
policy_class="sensitive" and memory_type="episode" only, or omit it entirely if it's just a passing mood.
- If nothing memorable is present, return an empty list.

Return ONLY valid JSON, no prose, no markdown fences, matching this schema:
{"memories": [{"memory_type": "...", "fact_text": "...", "entities": ["..."], "confidence": 0.0-1.0, "policy_class": "standard|sensitive|blocked"}]}
"""


def extract_candidates(event: InteractionEvent) -> list[dict]:
    if not event.text:
        return []

    llm = get_llm(temperature=0.0)

    response = llm.invoke(
        [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"User interaction: {event.text}"},
        ]
    )

    raw = response.content.strip()
    raw = (
        raw.removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )

    try:
        data = json.loads(raw)
        return data.get("memories", [])
    except json.JSONDecodeError:
        return []


def process_event(
    event: InteractionEvent,
    graph: GraphStore,
    vectors: VectorStore,
) -> list[MemoryFact]:
    """
    Full pipeline for one event:
    extract -> policy filter -> contradiction/correction handling
    -> graph write -> embed.

    Returns the memories that were persisted.
    """
    candidates = extract_candidates(event)
    written: list[MemoryFact] = []

    for c in candidates:
        policy_class = c.get("policy_class", "standard")

        if policy_class == "blocked":
            continue  # never persisted, per policy

        fact = MemoryFact(
            subject_id=event.subject_id,
            memory_type=MemoryType(c.get("memory_type", "episode")),
            fact_text=c["fact_text"],
            entities=c.get("entities", []),
            confidence=float(c.get("confidence", 0.5)),
            policy_class=PolicyClass(policy_class),
            source_event_id=event.event_id,
        )

        # Correction handling:
        # A correction represents a change to the user's previous
        # preference. Supersede active preference-like memories
        # regardless of whether their entities are identical.
        if fact.memory_type == MemoryType.CORRECTION:
            prior_memories = graph.get_active_memories(event.subject_id)

            for prior in prior_memories:
                prior_type = prior.get("memory_type")

                if prior_type in (
                    MemoryType.EXPLICIT_PREFERENCE.value,
                    MemoryType.CANDIDATE_PREFERENCE.value,
                    MemoryType.EXCLUSION.value,
                    MemoryType.CORRECTION.value,
                ):
                    graph.supersede_memory(
                        prior["memory_id"],
                        fact.memory_id,
                    )

        # Write the new memory after correction handling.
        graph.upsert_memory(fact)

        # Embed non-blocked memories so they remain available
        # for semantic retrieval.
        if fact.policy_class != PolicyClass.BLOCKED:
            vectors.upsert(
                fact.memory_id,
                fact.subject_id,
                fact.fact_text,
            )

        written.append(fact)

    return written