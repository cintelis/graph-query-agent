"""HTTP surface for the Auditor Console (mounted at ``/api``).

* ``GET  /api/projects``                 — project manifest (projects_list@1)
* ``GET  /api/intents``                  — the public registry, Cypher included
* ``GET  /api/projects/{pid}/options``   — id+name list for param dropdowns
* ``POST /api/ask``                      — deterministic question → intent match
* ``POST /api/execute``                  — run one registry template, with lineage
* ``GET  /api/projects/{pid}/graph``     — explorer-shaped nodes/edges (≤500)

``/api/ask`` is deliberately NOT an LLM: keyword overlap against each
intent's registered question patterns. When nothing matches well, the
console says so and offers the catalogue — it does not guess.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable, SessionExpired
from pydantic import BaseModel, Field

from app.auditor import executor
from app.auditor.intents import Intent, get_intent, public_intents

router = APIRouter(prefix="/api", tags=["auditor"])

_WORD_RE = re.compile(r"[a-z0-9@_./-]+")

# Below this overlap score the match is reported but flagged unconfident;
# the UI nudges the user toward explicit intent chips instead.
CONFIDENCE_THRESHOLD = 0.5


# --------------------------------------------------------------------- #
# request/response models
# --------------------------------------------------------------------- #
class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    projectId: str | None = None


class ExecuteRequest(BaseModel):
    intent: str = Field(min_length=1, description="intent ref, e.g. 'data_flow@1'")
    params: dict[str, str | None] = Field(default_factory=dict)


# --------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------- #
def _norm(token: str) -> str:
    """Fold trivial plurals so 'requirements' matches 'requirement'."""
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokens(text: str) -> set[str]:
    return {_norm(t) for t in _WORD_RE.findall(text.lower())}


def score_question(intent: Intent, question: str) -> float:
    """Deterministic keyword-overlap score in [0, 1].

    For each registered pattern: fraction of its keywords present in the
    question (after trivial plural folding). The intent's score is its
    best pattern's score.
    """
    words = _tokens(question)
    best = 0.0
    for pattern in intent.question_patterns:
        if not pattern:
            continue
        hit = sum(1 for kw in pattern if _norm(kw) in words)
        best = max(best, hit / len(pattern))
    return round(best, 3)


def match_question(question: str) -> list[tuple[Intent, float]]:
    scored = [(i, score_question(i, question)) for i in public_intents()]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


async def _run(intent: Intent, params: dict) -> dict:
    """Execute a registry template, translating failures into HTTP errors."""
    try:
        return await executor.execute(intent, params)
    except executor.ParamError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=502, detail=f"neo4j auth failed: {exc}") from exc
    except (ServiceUnavailable, SessionExpired, OSError) as exc:
        raise HTTPException(status_code=503, detail=f"neo4j unreachable: {exc}") from exc
    except Neo4jError as exc:
        raise HTTPException(status_code=502, detail=f"neo4j error: {exc.code}: {exc.message}") from exc


def _require_intent(ref: str) -> Intent:
    intent = get_intent(ref)
    if intent is None or intent.hidden:
        raise HTTPException(status_code=404, detail=f"unknown intent '{ref}' — see GET /api/intents")
    return intent


# --------------------------------------------------------------------- #
# routes
# --------------------------------------------------------------------- #
@router.get("/projects")
async def projects() -> dict:
    """Manifest of every project graph, via the projects_list@1 template."""
    return await _run(get_intent("projects_list@1"), {})


@router.get("/intents")
async def intents() -> dict:
    """The whole query surface. Cypher included — showing it is the product."""
    return {
        "intents": [i.to_dict() for i in public_intents()],
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "read_only": True,
    }


@router.get("/projects/{pid}/options")
async def options(pid: str, kind: str = Query(default="*", max_length=40)) -> dict:
    """id + name of nodes of one kind (or '*'), for param dropdowns."""
    if not re.fullmatch(r"[A-Z_]+|\*", kind):
        raise HTTPException(status_code=422, detail="kind must be a DesignNode kind or '*'")
    return await _run(get_intent("_options@1"), {"projectId": pid, "kind": kind})


@router.post("/ask")
async def ask(body: AskRequest) -> dict:
    """Deterministically match a free-text question to a registered intent."""
    scored = match_question(body.question)
    best_intent, confidence = scored[0] if scored else (None, 0.0)
    if best_intent is None or confidence <= 0.0:
        return {
            "matched_intent": None,
            "confidence": 0.0,
            "missing_params": [],
            "candidates": [],
            "note": "No registered intent matches. This console does not guess — pick one from the catalogue.",
        }

    provided = {"projectId"} if body.projectId else set()
    missing = [
        p.name
        for p in best_intent.params
        if p.required and p.name not in provided
    ]
    return {
        "matched_intent": best_intent.to_dict(),
        "confidence": confidence,
        "confident": confidence >= CONFIDENCE_THRESHOLD,
        "missing_params": missing,
        "candidates": [
            {"intent": i.ref, "title": i.title, "confidence": s}
            for i, s in scored[:3]
            if s > 0.0
        ],
    }


@router.post("/execute")
async def execute(body: ExecuteRequest) -> dict:
    """Run one registered read-only template with bound params + lineage."""
    intent = _require_intent(body.intent)
    return await _run(intent, dict(body.params))


@router.get("/projects/{pid}/graph")
async def graph(pid: str) -> dict:
    """Explorer-compatible {nodes, edges} for one project, capped at 500 nodes."""
    envelope = await _run(get_intent("_graph@1"), {"projectId": pid})
    rows = envelope["rows"]
    nodes = rows[0]["nodes"] if rows else []
    edges = rows[0]["edges"] if rows else []
    return {"nodes": nodes, "edges": edges, "lineage": envelope["lineage"]}
