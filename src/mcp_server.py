"""
MCP server exposing narrow, authenticated memory tools to the model — never
a generic graph query tool. Run with: python -m src.mcp_server
"""
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import json

from src.graph_store import GraphStore
from src.vector_store import VectorStore
from src.retrieval import retrieve
from src.models import MemoryFact, MemoryType, PolicyClass

server = Server("spotify-memory-mcp")
graph = GraphStore()
vectors = VectorStore()


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_memory",
            description="Retrieve relevant stored memories for a subject given the current intent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_id": {"type": "string"},
                    "intent": {"type": "string"},
                },
                "required": ["subject_id", "intent"],
            },
        ),
        Tool(
            name="add_explicit_preference",
            description="Store a preference the user directly and explicitly stated.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_id": {"type": "string"},
                    "fact_text": {"type": "string"},
                    "entities": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["subject_id", "fact_text"],
            },
        ),
        Tool(
            name="correct_memory",
            description="Supersede an existing memory with a corrected fact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "old_memory_id": {"type": "string"},
                    "subject_id": {"type": "string"},
                    "corrected_fact_text": {"type": "string"},
                    "entities": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["old_memory_id", "subject_id", "corrected_fact_text"],
            },
        ),
        Tool(
            name="delete_memory",
            description="Delete a memory (soft-delete; excluded from all future retrieval).",
            inputSchema={
                "type": "object",
                "properties": {"memory_id": {"type": "string"}},
                "required": ["memory_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "search_memory":
        results = retrieve(arguments["subject_id"], arguments["intent"], graph, vectors)
        payload = [
            {
                "memory_id": r.memory.memory_id,
                "fact": r.memory.fact_text,
                "type": r.memory.memory_type.value,
                "confidence": r.memory.confidence,
                "relevance_score": r.relevance_score,
                "reason": r.relevance_reason,
            }
            for r in results
        ]
        return [TextContent(type="text", text=json.dumps(payload, indent=2))]

    if name == "add_explicit_preference":
        fact = MemoryFact(
            subject_id=arguments["subject_id"],
            memory_type=MemoryType.EXPLICIT_PREFERENCE,
            fact_text=arguments["fact_text"],
            entities=arguments.get("entities", []),
            confidence=0.95,
            policy_class=PolicyClass.STANDARD,
        )
        graph.upsert_memory(fact)
        vectors.upsert(fact.memory_id, fact.subject_id, fact.fact_text)
        return [TextContent(type="text", text=json.dumps({"memory_id": fact.memory_id, "status": "created"}))]

    if name == "correct_memory":
        new_fact = MemoryFact(
            subject_id=arguments["subject_id"],
            memory_type=MemoryType.CORRECTION,
            fact_text=arguments["corrected_fact_text"],
            entities=arguments.get("entities", []),
            confidence=0.95,
            policy_class=PolicyClass.STANDARD,
        )
        graph.upsert_memory(new_fact)
        graph.supersede_memory(arguments["old_memory_id"], new_fact.memory_id)
        vectors.upsert(new_fact.memory_id, new_fact.subject_id, new_fact.fact_text)
        return [TextContent(type="text", text=json.dumps({"new_memory_id": new_fact.memory_id, "status": "superseded_old"}))]

    if name == "delete_memory":
        graph.delete_memory(arguments["memory_id"])
        vectors.delete(arguments["memory_id"])
        return [TextContent(type="text", text=json.dumps({"memory_id": arguments["memory_id"], "status": "deleted"}))]

    return [TextContent(type="text", text=json.dumps({"error": f"unknown tool {name}"}))]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
