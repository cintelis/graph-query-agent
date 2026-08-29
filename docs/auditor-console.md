# Auditor Console

A live demo extension: ask governed, deterministic, **read-only** questions
about a software DesignGraph stored in an external Neo4j — the
swarm-of-agents platform's database — and get answers with full lineage.
The pitch: AI-generated software you can *audit*. Every answer shows the
exact reviewed Cypher template that produced it, the bound parameters, the
graph version it was answered from, and a request id — nothing is guessed,
nothing is written.

## Pieces

| Piece | Path |
| --- | --- |
| Intent registry (the whole query surface) | `backend/app/auditor/intents.py` |
| Read-only executor + lineage stamping | `backend/app/auditor/executor.py` |
| HTTP surface (`/api/*`) | `backend/app/auditor/router.py` |
| Console UI (static, no build step) | `auditor-console.html` |
| Optional local sample graph | `infra/neo4j/seed-designgraph-sample.cypher` |

## The strict read-only guarantee

The target database belongs to another platform. Three independent layers
keep this console from ever mutating it:

1. **Registry-only execution** — the executor runs `Intent` objects from
   the registry and nothing else; there is no code path that accepts
   caller-supplied Cypher.
2. **Templates are MATCH/RETURN only** — every registered template is
   reviewed, parameterized and contains no write clause. The Cypher is
   returned in every response and shown in the UI: showing the query *is*
   the product.
3. **READ-access sessions** — every Neo4j session is opened with
   `default_access_mode=READ`, so the server itself rejects writes even if
   layers 1–2 were somehow bypassed.

`/api/ask` is deliberately **not an LLM**: it is keyword-overlap scoring
against each intent's registered `question_patterns`. Below the confidence
threshold the console flags the match and offers the catalogue — it asks
rather than guesses.

## Running it

Prerequisite: a reachable Neo4j holding a DesignGraph
(`:DesignNode` / `:DESIGN_EDGE`, scoped by `projectId`).

```bash
cd backend
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Point at the swarm-of-agents platform Neo4j (read-only usage):
cat > .env <<'EOF'
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=agent-neo4j
EOF

uvicorn app.main:app --reload --port 8000
```

Then open `auditor-console.html` (double-click, or any static server —
CORS is permissive for the local demo). The console defaults to backend
`http://localhost:8000`. Postgres is **not** required for any `/api/*`
route; only the pre-existing `/ready` probe touches it.

### Demo without the platform (sample graph)

If the swarm Neo4j is not running, use the repo's throwaway stack
(remapped ports 7475/7688, so it never collides with the platform):

```bash
docker compose -f infra/docker-compose.yml up -d neo4j
cat infra/neo4j/seed-designgraph-sample.cypher | \
  docker exec -i orchestration-agent-neo4j-1 cypher-shell -u neo4j -p orchestrator
# .env: NEO4J_URI=bolt://localhost:7688, NEO4J_PASSWORD=orchestrator
```

The seed creates project `beacon-demo@intent` (31 nodes / 40 edges). It is
for the local demo DB only — never load it into the platform database.

## API

| Route | What |
| --- | --- |
| `GET /api/projects` | Manifest of project graphs (node/edge counts, last update) |
| `GET /api/intents` | The registry — params, patterns and full Cypher included |
| `GET /api/projects/{pid}/options?kind=REQUIREMENT` | id+name lists for param dropdowns (`kind=*` for all) |
| `POST /api/ask` `{question, projectId}` | Deterministic match → `{matched_intent, confidence, missing_params}` |
| `POST /api/execute` `{intent, params}` | Rows + columns + cypher + params + `lineage{request_id, graph_version, timing_ms, attempts, produced_by, source}` |
| `GET /api/projects/{pid}/graph` | Explorer-shaped `{nodes:[{id,type,label}], edges:[{s,t,rel}]}`, ≤500 nodes |

## Demo script (investor walkthrough)

1. **"What project graphs exist?"** — connect; the Scope selector fills
   from `/api/projects`. Point at the manifest: counts + graph version.
2. Ask **"what requirements are implemented, and by which code?"** →
   matches `requirement_implementations@1`. Show the confidence meter,
   then the param form (requirement dropdown populated live from the
   graph). Run — every implementing class/method with status, provenance
   (ARCHITECT vs ENGINEER) and target file.
3. Ask **"where is the data stored — what reads and writes it?"** →
   `data_flow@1`. The data plane as source → edge → target rows.
4. Ask **"what endpoints are exposed and under which contract?"** →
   `contract_surface@1`.
5. Ask **"what is not yet verified?"** → `unverified_work@1`. The honest
   slide: exactly what remains unproven, grouped by status and kind.
6. Ask **"what breaks if I change TelemetryService?"** → `blast_radius@1`
   with the node picked from a dropdown; 3-hop incoming
   DEPENDS_ON/CALLS/CONSUMES with hop distance.
7. Close on the evidence pane: the green **read-only** badge on the exact
   Cypher, and the lineage card — request id, graph version, timing,
   `produced_by: intent@version`, `source: neo4j`. Every answer is
   reproducible and attributable; none of it was improvised.
