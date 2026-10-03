# Spotify Personalized AI Memory System — MVP
<img width="6016" height="4016" alt="thibault-penin-SwKf1x2_hRo-unsplash" src="https://github.com/user-attachments/assets/9c5eb10d-a687-4632-8c70-0d6925b7380f" />


A working scaffold of the governed AI memory system described in the product
spec: event capture → memory extraction (LLM) → temporal graph write (Neo4j)
→ embeddings (Qdrant) → hybrid retrieval → policy-filtered context →
LangGraph agent → response, plus an MCP server exposing narrow memory tools.

This is a lean MVP, not the full enterprise build (no Kafka, no Next.js
consoles, no Kubernetes) — it proves the core lifecycle end-to-end so you can
extend it piece by piece.

## Architecture

```
User message
   │
   ▼
[capture]  → LLM extracts candidate memories → Neo4j (graph) + Qdrant (vectors)
   │
   ▼
[retrieve] → hybrid graph + vector search → reranked → context package
   │
   ▼
[generate] → LLM responds using memory as data, never as instructions
```

Core files:
- `src/models.py` — typed contracts (events, memory facts, context package)
- `src/graph_store.py` — Neo4j temporal graph (valid-time, supersession)
- `src/vector_store.py` — Qdrant embeddings, keyed by the same memory_id
- `src/memory_processor.py` — LLM-based extraction + policy filtering
- `src/retrieval.py` — hybrid candidate generation + reranking
- `src/context_composer.py` — bounded, policy-filtered context + no-memory fallback
- `src/agent.py` — LangGraph workflow: capture → retrieve → generate
- `src/mcp_server.py` — MCP tools: `search_memory`, `add_explicit_preference`,
  `correct_memory`, `delete_memory`
- `src/main.py` — demo script, run this first

## Setup

### 1. Start Neo4j + Qdrant

```bash
docker-compose up -d
```

Wait ~20s for Neo4j to be healthy. Check the browser UI at
http://localhost:7474 (user: `neo4j`, password: `password123`).

### 2. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Open `.env` and paste your Groq API key into `GROQ_API_KEY`.
Get a free key at https://console.groq.com/keys if you don't have one.

### 4. Run the terminal demo (optional, no frontend needed)

```bash
python -m src.main
```

You should see a 4-turn conversation where:
- Turn 1 states an explicit preference (instrumental, no lyrics) → stored.
- Turn 2 retrieves that preference and personalizes the suggestion.
- Turn 3 corrects the preference → old fact is superseded, not deleted.
- Turn 4 retrieves the corrected preference, not the old one.

### 5. Run the full app locally (backend API + async worker + frontend UI)

**Terminal A — backend API (chat + memory CRUD):**

```bash
uvicorn src.api:app --reload --port 8000
```

**Terminal B — async memory worker (consumes Kafka, writes to Neo4j + Qdrant):**

```bash
python -m src.worker
```

This is the asynchronous half of ingestion: the chat path only publishes an
event to Kafka and returns immediately; this worker does the LLM extraction
and graph/vector writes in the background. (If Kafka isn't running, the
agent falls back to writing synchronously so the app still works end to end
— see `src/agent.py`.)

**Terminal C — frontend:**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 — chat panel on the left, "Remembered so far"
memory panel on the right.

### 6. Deploying to Kubernetes (production path)

The `k8s/` folder has manifests for every service in the architecture:
Neo4j, Qdrant, Kafka+Zookeeper, the backend API, the async worker, and the
frontend. To use them:

```bash
# 1. Build and push your own images (replace "your-registry" in the YAML)
docker build -t your-registry/spotify-memory-api:latest -f Dockerfile.api .
docker build -t your-registry/spotify-memory-frontend:latest ./frontend
docker push your-registry/spotify-memory-api:latest
docker push your-registry/spotify-memory-frontend:latest

# 2. Set your real Groq key in k8s/01-config-and-secrets.yaml

# 3. Apply everything in order
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-config-and-secrets.yaml
kubectl apply -f k8s/02-neo4j.yaml
kubectl apply -f k8s/03-qdrant.yaml
kubectl apply -f k8s/04-kafka.yaml
kubectl apply -f k8s/05-backend.yaml
kubectl apply -f k8s/06-frontend.yaml

# 4. Check everything is up
kubectl get pods -n spotify-memory
```

These manifests are a solid starting point, not a production-hardened
config — you'd still want to add resource-based autoscaling, network
policies, and a real ingress/TLS setup before going live.

### 7. (Optional) Run the MCP server standalone

```bash
python -m src.mcp_server
```

This exposes the four memory tools over stdio for any MCP-compatible client
(e.g. Claude Desktop, or your own LangGraph agent via an MCP client adapter).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `RuntimeError: GROQ_API_KEY not set` | You didn't copy `.env.example` to `.env`, or forgot to paste the key |
| Neo4j connection refused | `docker-compose up -d` not run yet, or still starting — wait and retry |
| Qdrant connection error | Same — check `docker ps` shows `memory-qdrant` running |
| Empty/garbage extraction JSON | Some Groq models are chattier than others; `llama-3.3-70b-versatile` follows the JSON-only instruction reliably — swap `GROQ_MODEL` if you changed it |

## Project layout

```
spotify-memory-system/
├── src/                    # Python backend
│   ├── api.py               # FastAPI REST layer (chat + memory CRUD)
│   ├── agent.py              # LangGraph workflow
│   ├── kafka_producer.py      # publishes events (async capture)
│   ├── worker.py               # Kafka consumer: extraction + graph/vector writes
│   ├── mcp_server.py            # MCP tools
│   ├── memory_processor.py, retrieval.py, context_composer.py
│   ├── graph_store.py, vector_store.py
│   └── main.py                  # terminal demo, no API/frontend needed
├── frontend/                 # Next.js Memory Console
│   └── app/ ...
├── k8s/                       # Kubernetes manifests (Neo4j, Qdrant, Kafka, API, worker, frontend)
├── Dockerfile.api              # backend image (used by API + worker deployments)
├── frontend/Dockerfile          # frontend image
├── docker-compose.yml            # local dev: Kafka+Zookeeper, Neo4j, Qdrant
└── requirements.txt
```

## What's implemented vs. the full spec

| Spec requirement | Status |
|---|---|
| LLM extraction, LangChain, LangGraph agent | ✅ |
| Temporal graph (Neo4j), valid-time, correction/supersession | ✅ |
| Embeddings + hybrid retrieval (Qdrant) | ✅ |
| MCP tools (search/add/correct/delete) | ✅ |
| Asynchronous capture via Kafka, synchronous retrieval | ✅ |
| REST API + Next.js console | ✅ |
| Kubernetes deployment manifests | ✅ (starting point, not production-hardened) |
| OpenTelemetry tracing, Prometheus/Grafana dashboards | ❌ not included |
| Consent/geography/age-based policy engine | ❌ only basic sensitive/blocked policy classes |
| Golden evaluation set + automated precision/recall scoring | ❌ not included |
| Multiple product consoles (ops monitor, policy panel, schema console) | ❌ only the Memory Console (chat + memory list) |

## Next steps to reach 100% of the spec

- Swap the synchronous `process_event` call in the agent for a Kafka/Redpanda
  queue + idempotency keys, so the chat path doesn't wait on graph writes
- Add the Memory Control settings view, context-preview panel, and
  policy/schema consoles described in spec section `5.2`
- Add OpenTelemetry tracing per the observability requirements
- Add the golden evaluation set and precision/recall scoring (`7.7 Testing Approach`)
- Add consent/retention/geography policy enforcement before retrieval
