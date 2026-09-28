"""
Demo entrypoint. Run: python -m src.main
Simulates a multi-turn conversation to show memory being created,
retrieved, and reused across turns.
"""
from src.graph_store import GraphStore
from src.vector_store import VectorStore
from src.agent import build_agent

SUBJECT_ID = "user_demo_001"

DEMO_TURNS = [
    "I always want low-vocal, instrumental focus music when I'm working, no lyrics please.",
    "Can you suggest something for me to focus on coding right now?",
    "Actually, I don't mind vocals anymore, I changed my mind — I like lo-fi with soft vocals now.",
    "What should I listen to while I code today?",
]


def main():
    graph = GraphStore()
    vectors = VectorStore()
    agent = build_agent(graph, vectors)

    print(f"\n=== Session for {SUBJECT_ID} ===\n")
    for i, turn in enumerate(DEMO_TURNS, start=1):
        print(f"--- Turn {i} ---")
        print(f"User: {turn}")
        result = agent.invoke({"subject_id": SUBJECT_ID, "user_message": turn})
        print(f"Assistant: {result['response']}\n")

    graph.close()


if __name__ == "__main__":
    main()
