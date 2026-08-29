"""Declarative intent registry for the Auditor Console.

Every question the console can answer is a *registered intent*: a reviewed,
versioned, parameterized Cypher template. The registry is the entire query
surface — the executor refuses anything that is not in here, and every
template is read-only (MATCH/RETURN only, no write clauses).

Matching a free-text question to an intent is deliberately deterministic:
keyword overlap against ``question_patterns``, no LLM. The console asks
rather than guesses.

DesignGraph schema (external — the swarm-of-agents platform's Neo4j):

* nodes:  ``(:DesignNode)`` with ``projectId``, ``id``, ``kind``, ``name``,
  ``description``, ``status`` (PLANNED|IMPLEMENTED|VERIFIED), ``provenance``
  (ARCHITECT|ENGINEER), ``metadataJson`` (JSON string, may be missing),
  ``createdAt``/``updatedAt`` (ISO-8601 strings). Optional props may be
  absent — templates read defensively via ``coalesce``.
* edges:  ``[:DESIGN_EDGE]`` with ``projectId``, ``kind`` (CONTAINS,
  IMPLEMENTS, PERSISTS_TO, EXPOSES, HAS_CONTRACT, DEPENDS_ON, CALLS,
  CONSUMES, READS, WRITES, ...) and the same audit props.
* scoping: by the ``projectId`` property on EVERY node and edge.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Param:
    """One parameter of an intent template."""

    name: str
    type: str  # "string"
    required: bool
    description: str  # includes how-to-populate guidance
    # When set, the UI can populate a dropdown from
    # GET /api/projects/{pid}/options?kind=<options_kind>.
    options_kind: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "description": self.description,
            "options_kind": self.options_kind,
        }


@dataclass(frozen=True)
class Intent:
    """A reviewed, versioned, read-only Cypher template."""

    id: str
    version: int
    title: str
    description: str
    # Each pattern is a list of lowercase keywords; a question scores against
    # a pattern by keyword overlap (see match_question in the router).
    question_patterns: list[list[str]]
    params: list[Param]
    cypher: str
    read_only: bool = True
    # Hidden templates back fixed endpoints (options/graph) and are not
    # listed in the public catalogue nor matchable from free text.
    hidden: bool = field(default=False)

    @property
    def ref(self) -> str:
        """Canonical ``id@version`` reference, e.g. ``projects_list@1``."""
        return f"{self.id}@{self.version}"

    def to_dict(self) -> dict:
        # Cypher is included on purpose: showing the exact query that will
        # run — before it runs — is the product.
        return {
            "intent": self.ref,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "read_only": self.read_only,
            "params": [p.to_dict() for p in self.params],
            "cypher": self.cypher,
            "question_patterns": self.question_patterns,
        }


_PROJECT_PARAM = Param(
    name="projectId",
    type="string",
    required=True,
    description="DesignGraph project scope, e.g. 'app@intent'. Populate from GET /api/projects.",
)


INTENTS: list[Intent] = [
    # ------------------------------------------------------------------ #
    Intent(
        id="projects_list",
        version=1,
        title="Project manifest",
        description=(
            "Every project graph in the database: projectId, node count, "
            "edge count and the most recent update timestamp (the graph "
            "version used in lineage)."
        ),
        question_patterns=[
            ["projects", "list"],
            ["which", "projects"],
            ["what", "projects", "exist"],
            ["show", "project", "graphs"],
            ["manifest"],
        ],
        params=[],
        cypher=(
            "MATCH (n:DesignNode)\n"
            "WHERE n.projectId IS NOT NULL\n"
            "WITH n.projectId AS projectId, count(n) AS nodeCount,\n"
            "     max(coalesce(n.updatedAt, '')) AS lastNodeUpdate\n"
            "OPTIONAL MATCH ()-[r:DESIGN_EDGE]->() WHERE r.projectId = projectId\n"
            "WITH projectId, nodeCount, lastNodeUpdate, count(r) AS edgeCount,\n"
            "     max(coalesce(r.updatedAt, '')) AS lastEdgeUpdate\n"
            "RETURN projectId, nodeCount, edgeCount,\n"
            "       CASE WHEN lastEdgeUpdate > lastNodeUpdate\n"
            "            THEN lastEdgeUpdate ELSE lastNodeUpdate END AS lastUpdated\n"
            "ORDER BY projectId"
        ),
    ),
    # ------------------------------------------------------------------ #
    Intent(
        id="requirement_implementations",
        version=1,
        title="Requirement → implementation",
        description=(
            "For a requirement (by id, or by name fragment, or all of them): "
            "every node that reaches it via an IMPLEMENTS edge, with kind, "
            "name, status, provenance and the target file when the "
            "implementing node's metadataJson records one."
        ),
        question_patterns=[
            ["requirement", "implemented"],
            ["what", "implements", "requirement"],
            ["who", "implements"],
            ["implementation", "requirement"],
            ["requirement", "coverage"],
            ["code", "satisfies", "requirement"],
        ],
        params=[
            _PROJECT_PARAM,
            Param(
                name="requirementId",
                type="string",
                required=False,
                description=(
                    "Exact REQUIREMENT node id. Populate from "
                    "GET /api/projects/{pid}/options?kind=REQUIREMENT. "
                    "Leave empty to use a name fragment or list all."
                ),
                options_kind="REQUIREMENT",
            ),
            Param(
                name="requirementName",
                type="string",
                required=False,
                description=(
                    "Case-insensitive fragment of the requirement name, "
                    "e.g. 'audit'. Ignored when requirementId is given."
                ),
            ),
        ],
        cypher=(
            "MATCH (req:DesignNode {projectId: $projectId, kind: 'REQUIREMENT'})\n"
            "WHERE ($requirementId IS NULL OR req.id = $requirementId)\n"
            "  AND ($requirementId IS NOT NULL OR $requirementName IS NULL\n"
            "       OR toLower(coalesce(req.name, '')) CONTAINS toLower($requirementName))\n"
            "OPTIONAL MATCH (impl:DesignNode {projectId: $projectId})\n"
            "               -[e:DESIGN_EDGE {kind: 'IMPLEMENTS'}]->(req)\n"
            "WHERE e.projectId = $projectId\n"
            "RETURN req.id AS requirementId,\n"
            "       coalesce(req.name, '')        AS requirement,\n"
            "       coalesce(req.status, '')      AS requirementStatus,\n"
            "       impl.kind                     AS implementedByKind,\n"
            "       impl.name                     AS implementedBy,\n"
            "       impl.status                   AS implementationStatus,\n"
            "       impl.provenance               AS provenance,\n"
            "       impl.metadataJson             AS metadataJson\n"
            "ORDER BY requirementId, implementedByKind, implementedBy"
        ),
    ),
    # ------------------------------------------------------------------ #
    Intent(
        id="data_flow",
        version=1,
        title="Data plane",
        description=(
            "The data plane of a project: TYPE→TABLE persistence "
            "(PERSISTS_TO), READS/WRITES edges, and TABLE→COLUMN structure "
            "(CONTAINS), as source → edge → target rows. Optionally filtered "
            "by an entity-name fragment."
        ),
        question_patterns=[
            ["data", "flow"],
            ["where", "data", "stored"],
            ["what", "reads", "writes"],
            ["persists", "table"],
            ["database", "tables", "columns"],
            ["data", "plane"],
        ],
        params=[
            _PROJECT_PARAM,
            Param(
                name="entityName",
                type="string",
                required=False,
                description=(
                    "Case-insensitive name fragment matched against either "
                    "end of the edge, e.g. 'telemetry'. Leave empty for the "
                    "whole data plane."
                ),
            ),
        ],
        cypher=(
            "MATCH (src:DesignNode {projectId: $projectId})\n"
            "      -[e:DESIGN_EDGE]->(dst:DesignNode {projectId: $projectId})\n"
            "WHERE e.projectId = $projectId\n"
            "  AND ((e.kind = 'PERSISTS_TO' AND src.kind = 'TYPE' AND dst.kind = 'TABLE')\n"
            "       OR e.kind IN ['READS', 'WRITES']\n"
            "       OR (e.kind = 'CONTAINS' AND src.kind = 'TABLE' AND dst.kind = 'COLUMN'))\n"
            "  AND ($entityName IS NULL\n"
            "       OR toLower(coalesce(src.name, '')) CONTAINS toLower($entityName)\n"
            "       OR toLower(coalesce(dst.name, '')) CONTAINS toLower($entityName))\n"
            "RETURN src.kind                  AS sourceKind,\n"
            "       coalesce(src.name, '')    AS source,\n"
            "       e.kind                    AS edge,\n"
            "       dst.kind                  AS targetKind,\n"
            "       coalesce(dst.name, '')    AS target,\n"
            "       coalesce(dst.status, '')  AS targetStatus\n"
            "ORDER BY edge, source, target"
        ),
    ),
    # ------------------------------------------------------------------ #
    Intent(
        id="contract_surface",
        version=1,
        title="Contract surface",
        description=(
            "Every ENDPOINT node in the project, the node that EXPOSES it, "
            "and its HAS_CONTRACT target — the externally promised surface."
        ),
        question_patterns=[
            ["endpoints", "exposed"],
            ["api", "surface"],
            ["contract", "surface"],
            ["what", "endpoints"],
            ["who", "exposes"],
            ["public", "api", "contracts"],
        ],
        params=[_PROJECT_PARAM],
        cypher=(
            "MATCH (ep:DesignNode {projectId: $projectId, kind: 'ENDPOINT'})\n"
            "OPTIONAL MATCH (owner:DesignNode {projectId: $projectId})\n"
            "               -[x:DESIGN_EDGE {kind: 'EXPOSES'}]->(ep)\n"
            "WHERE x.projectId = $projectId\n"
            "OPTIONAL MATCH (ep)-[h:DESIGN_EDGE {kind: 'HAS_CONTRACT'}]\n"
            "               ->(c:DesignNode {projectId: $projectId})\n"
            "WHERE h.projectId = $projectId\n"
            "RETURN coalesce(ep.name, '')    AS endpoint,\n"
            "       coalesce(ep.status, '')  AS status,\n"
            "       owner.kind               AS exposedByKind,\n"
            "       owner.name               AS exposedBy,\n"
            "       c.kind                   AS contractKind,\n"
            "       c.name                   AS contract\n"
            "ORDER BY endpoint"
        ),
    ),
    # ------------------------------------------------------------------ #
    Intent(
        id="unverified_work",
        version=1,
        title="Unverified work",
        description=(
            "Everything not yet proven: nodes whose status is not VERIFIED, "
            "grouped by status and kind, with example names."
        ),
        question_patterns=[
            ["not", "verified"],
            ["unverified"],
            ["what", "unproven"],
            ["outstanding", "work"],
            ["planned", "implemented", "verified"],
            ["what", "left", "prove"],
        ],
        params=[_PROJECT_PARAM],
        cypher=(
            "MATCH (n:DesignNode {projectId: $projectId})\n"
            "WHERE coalesce(n.status, 'UNKNOWN') <> 'VERIFIED'\n"
            "RETURN coalesce(n.status, 'UNKNOWN') AS status,\n"
            "       n.kind                        AS kind,\n"
            "       count(n)                      AS count,\n"
            "       collect(coalesce(n.name, n.id))[..10] AS examples\n"
            "ORDER BY status, count DESC, kind"
        ),
    ),
    # ------------------------------------------------------------------ #
    Intent(
        id="blast_radius",
        version=1,
        title="Blast radius",
        description=(
            "Everything that would feel a change to one node: incoming "
            "DEPENDS_ON / CALLS / CONSUMES chains up to 3 hops, with hop "
            "distance. Capped at 200 rows."
        ),
        question_patterns=[
            ["blast", "radius"],
            ["what", "breaks", "change"],
            ["impact", "changing"],
            ["what", "depends", "on"],
            ["who", "calls"],
            ["downstream", "upstream", "impact"],
        ],
        params=[
            _PROJECT_PARAM,
            Param(
                name="nodeId",
                type="string",
                required=True,
                description=(
                    "Id of the node under change. Populate from "
                    "GET /api/projects/{pid}/options (any kind)."
                ),
                options_kind="*",
            ),
        ],
        cypher=(
            "MATCH (target:DesignNode {projectId: $projectId, id: $nodeId})\n"
            "MATCH p = (dep:DesignNode)-[rels:DESIGN_EDGE*1..3]->(target)\n"
            "WHERE dep.projectId = $projectId\n"
            "  AND all(r IN rels WHERE r.projectId = $projectId\n"
            "          AND r.kind IN ['DEPENDS_ON', 'CALLS', 'CONSUMES'])\n"
            "RETURN DISTINCT dep.id           AS id,\n"
            "       dep.kind                  AS kind,\n"
            "       coalesce(dep.name, '')    AS name,\n"
            "       coalesce(dep.status, '')  AS status,\n"
            "       length(p)                 AS hops\n"
            "ORDER BY hops, kind, name\n"
            "LIMIT 200"
        ),
    ),
    # ------------------------------------------------------------------ #
    # Hidden templates: back fixed endpoints; not in the public catalogue.
    Intent(
        id="_options",
        version=1,
        title="Param options (internal)",
        description="id + name of nodes of one kind, for param dropdowns.",
        question_patterns=[],
        params=[
            _PROJECT_PARAM,
            Param("kind", "string", True, "DesignNode kind, e.g. REQUIREMENT."),
        ],
        cypher=(
            "MATCH (n:DesignNode {projectId: $projectId})\n"
            "WHERE $kind = '*' OR n.kind = $kind\n"
            "RETURN n.id AS id, coalesce(n.name, n.id) AS name, n.kind AS kind\n"
            "ORDER BY kind, name\n"
            "LIMIT 500"
        ),
        hidden=True,
    ),
    Intent(
        id="_graph",
        version=1,
        title="Project graph (internal)",
        description="Explorer-shaped nodes + edges for one project, capped at 500 nodes.",
        question_patterns=[],
        params=[_PROJECT_PARAM],
        cypher=(
            "MATCH (n:DesignNode {projectId: $projectId})\n"
            "WITH n ORDER BY n.kind, n.name LIMIT 500\n"
            "WITH collect(n) AS ns\n"
            "CALL {\n"
            "  WITH ns\n"
            "  UNWIND ns AS n\n"
            "  MATCH (n)-[r:DESIGN_EDGE]->(m:DesignNode)\n"
            "  WHERE r.projectId = $projectId AND m IN ns\n"
            "  RETURN collect({s: n.id, t: m.id, rel: r.kind}) AS es\n"
            "}\n"
            "RETURN [x IN ns | {id: x.id, type: x.kind, label: coalesce(x.name, x.id)}] AS nodes,\n"
            "       es AS edges"
        ),
        hidden=True,
    ),
]


# Lookup by canonical ref ("projects_list@1") and by bare id ("projects_list",
# resolving to the highest registered version).
_BY_REF: dict[str, Intent] = {i.ref: i for i in INTENTS}
_BY_ID: dict[str, Intent] = {}
for _i in INTENTS:
    if _i.id not in _BY_ID or _i.version > _BY_ID[_i.id].version:
        _BY_ID[_i.id] = _i


def get_intent(ref: str) -> Intent | None:
    """Resolve ``id@version`` or bare ``id`` (latest version) to an Intent."""
    return _BY_REF.get(ref) or _BY_ID.get(ref)


def public_intents() -> list[Intent]:
    return [i for i in INTENTS if not i.hidden]
