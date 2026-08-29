// =====================================================================
// Auditor Console — OPTIONAL sample DesignGraph seed
// ---------------------------------------------------------------------
// FOR THE LOCAL DEMO DATABASE ONLY. Never run this against the
// swarm-of-agents platform Neo4j (bolt://localhost:7687) — the console
// is strictly read-only against that database. This file exists so the
// Auditor Console can be demoed without the platform running, e.g.
// against the throwaway Neo4j from infra/docker-compose.yml
// (bolt://localhost:7688). It is not auto-run anywhere; load by hand:
//
//   cat infra/neo4j/seed-designgraph-sample.cypher | \
//     docker exec -i orchestration-agent-neo4j-1 \
//       cypher-shell -u neo4j -p orchestrator
//
// Shape matches the swarm platform's DesignGraph exactly:
//   (:DesignNode {projectId, id, kind, name, status, provenance,
//                 metadataJson, createdAt, updatedAt, ...})
//   -[:DESIGN_EDGE {projectId, id, srcId, dstId, kind, provenance,
//                   createdAt, updatedAt, ...}]->
// Some optional props are deliberately omitted on some rows to mirror
// real writers (the console must read defensively).
//
// Project: beacon-demo@intent — a small telemetry/alerting service.
// Idempotent: MERGE on (projectId, id).
// =====================================================================

// ---------- nodes (31) ----------
UNWIND [
  {id:'sys-beacon',        kind:'SYSTEM',    name:'Beacon',                          status:'VERIFIED',    provenance:'ARCHITECT', description:'Device telemetry ingestion + alerting platform', metadataJson:'{}', createdAt:'2026-06-20T09:00:00Z', updatedAt:'2026-07-10T09:00:00Z'},
  {id:'cont-api',          kind:'CONTAINER', name:'beacon-api',                      status:'IMPLEMENTED', provenance:'ARCHITECT', description:'Spring Boot HTTP API',                            metadataJson:'{}', createdAt:'2026-06-20T09:05:00Z', updatedAt:'2026-07-11T10:00:00Z'},
  {id:'cont-worker',       kind:'CONTAINER', name:'beacon-worker',                   status:'IMPLEMENTED', provenance:'ARCHITECT', description:'Async alert evaluation worker',                   metadataJson:'{}', createdAt:'2026-06-20T09:05:00Z', updatedAt:'2026-07-11T10:00:00Z'},

  {id:'req-1',             kind:'REQUIREMENT', name:'Ingest device telemetry',                 status:'VERIFIED',    provenance:'ARCHITECT', description:'Accept signed telemetry batches from field devices', metadataJson:'{}', createdAt:'2026-06-20T09:10:00Z', updatedAt:'2026-07-08T14:00:00Z'},
  {id:'req-2',             kind:'REQUIREMENT', name:'Raise alerts on threshold breach',        status:'IMPLEMENTED', provenance:'ARCHITECT', description:'Evaluate configured thresholds within 5s of ingest',  metadataJson:'{}', createdAt:'2026-06-20T09:10:00Z', updatedAt:'2026-07-09T11:30:00Z'},
  {id:'req-3',             kind:'REQUIREMENT', name:'Immutable audit log of alert decisions',  status:'PLANNED',     provenance:'ARCHITECT', description:'Every alert decision is written to an append-only audit log', metadataJson:'{}', createdAt:'2026-06-21T08:00:00Z', updatedAt:'2026-06-21T08:00:00Z'},

  {id:'type-telemetry-service', kind:'TYPE', name:'TelemetryService', status:'VERIFIED',    provenance:'ENGINEER', metadataJson:'{"file":"src/main/java/com/beacon/telemetry/TelemetryService.java"}', createdAt:'2026-06-22T10:00:00Z', updatedAt:'2026-07-08T14:00:00Z'},
  {id:'type-alert-service',     kind:'TYPE', name:'AlertService',     status:'IMPLEMENTED', provenance:'ENGINEER', metadataJson:'{"file":"src/main/java/com/beacon/alert/AlertService.java"}',         createdAt:'2026-06-22T10:00:00Z', updatedAt:'2026-07-09T11:30:00Z'},
  {id:'type-telemetry-record',  kind:'TYPE', name:'TelemetryRecord',  status:'VERIFIED',    provenance:'ENGINEER', metadataJson:'{"file":"src/main/java/com/beacon/telemetry/TelemetryRecord.java"}',  createdAt:'2026-06-22T10:05:00Z', updatedAt:'2026-07-08T14:00:00Z'},
  {id:'type-alert',             kind:'TYPE', name:'Alert',            status:'IMPLEMENTED', provenance:'ENGINEER', metadataJson:'{"file":"src/main/java/com/beacon/alert/Alert.java"}',                createdAt:'2026-06-23T09:00:00Z', updatedAt:'2026-07-09T11:30:00Z'},
  {id:'type-audit-writer',      kind:'TYPE', name:'AuditLogWriter',   status:'PLANNED',     provenance:'ARCHITECT', metadataJson:'{}',                                                                  createdAt:'2026-06-23T09:00:00Z', updatedAt:'2026-06-23T09:00:00Z'},

  {id:'meth-ingest',   kind:'METHOD', name:'TelemetryService.ingest',  status:'VERIFIED',    provenance:'ENGINEER', metadataJson:'{"file":"src/main/java/com/beacon/telemetry/TelemetryService.java","line":48}', createdAt:'2026-06-24T10:00:00Z', updatedAt:'2026-07-08T14:00:00Z'},
  {id:'meth-evaluate', kind:'METHOD', name:'AlertService.evaluate',    status:'IMPLEMENTED', provenance:'ENGINEER', metadataJson:'{"file":"src/main/java/com/beacon/alert/AlertService.java","line":62}',        createdAt:'2026-06-24T10:00:00Z', updatedAt:'2026-07-09T11:30:00Z'},

  {id:'ep-post-telemetry', kind:'ENDPOINT', name:'POST /telemetry', status:'VERIFIED',    provenance:'ENGINEER',  metadataJson:'{}', createdAt:'2026-06-24T11:00:00Z', updatedAt:'2026-07-08T14:00:00Z'},
  {id:'ep-get-alerts',     kind:'ENDPOINT', name:'GET /alerts',     status:'IMPLEMENTED', provenance:'ENGINEER',  metadataJson:'{}', createdAt:'2026-06-24T11:00:00Z', updatedAt:'2026-07-09T11:30:00Z'},
  {id:'ep-get-audit',      kind:'ENDPOINT', name:'GET /audit',      status:'PLANNED',     provenance:'ARCHITECT', metadataJson:'{}', createdAt:'2026-06-25T09:00:00Z', updatedAt:'2026-06-25T09:00:00Z'},

  {id:'tbl-telemetry', kind:'TABLE', name:'telemetry', status:'VERIFIED',    provenance:'ENGINEER', metadataJson:'{"schema":"public"}', createdAt:'2026-06-26T09:00:00Z', updatedAt:'2026-07-08T14:00:00Z'},
  {id:'tbl-alerts',    kind:'TABLE', name:'alerts',    status:'IMPLEMENTED', provenance:'ENGINEER', metadataJson:'{"schema":"public"}', createdAt:'2026-06-26T09:00:00Z', updatedAt:'2026-07-09T11:30:00Z'},

  // columns deliberately omit provenance/description/metadataJson
  {id:'col-t-id',      kind:'COLUMN', name:'telemetry.id',          status:'VERIFIED',    createdAt:'2026-06-26T09:10:00Z', updatedAt:'2026-07-08T14:00:00Z'},
  {id:'col-t-device',  kind:'COLUMN', name:'telemetry.device_id',   status:'VERIFIED',    createdAt:'2026-06-26T09:10:00Z', updatedAt:'2026-07-08T14:00:00Z'},
  {id:'col-t-ts',      kind:'COLUMN', name:'telemetry.recorded_at', status:'VERIFIED',    createdAt:'2026-06-26T09:10:00Z', updatedAt:'2026-07-08T14:00:00Z'},
  {id:'col-t-payload', kind:'COLUMN', name:'telemetry.payload',     status:'IMPLEMENTED', createdAt:'2026-06-26T09:10:00Z', updatedAt:'2026-07-09T11:30:00Z'},
  {id:'col-a-id',      kind:'COLUMN', name:'alerts.id',             status:'IMPLEMENTED', createdAt:'2026-06-26T09:15:00Z', updatedAt:'2026-07-09T11:30:00Z'},
  {id:'col-a-rule',    kind:'COLUMN', name:'alerts.rule',           status:'IMPLEMENTED', createdAt:'2026-06-26T09:15:00Z', updatedAt:'2026-07-09T11:30:00Z'},
  {id:'col-a-raised',  kind:'COLUMN', name:'alerts.raised_at',      status:'IMPLEMENTED', createdAt:'2026-06-26T09:15:00Z', updatedAt:'2026-07-09T11:30:00Z'},

  {id:'contract-openapi', kind:'CONTRACT',   name:'beacon-openapi.yaml',      status:'IMPLEMENTED', provenance:'ARCHITECT', metadataJson:'{"file":"contracts/beacon-openapi.yaml"}', createdAt:'2026-06-25T10:00:00Z', updatedAt:'2026-07-07T12:00:00Z'},
  // topic deliberately has NO status — exercises coalesce(status,'UNKNOWN')
  {id:'topic-readings',   kind:'TOPIC',      name:'readings.raw',                                   provenance:'ARCHITECT', metadataJson:'{}',                                       createdAt:'2026-06-25T10:00:00Z', updatedAt:'2026-07-05T09:00:00Z'},
  {id:'cfg-thresholds',   kind:'CONFIG',     name:'alert-thresholds.yml',     status:'IMPLEMENTED', provenance:'ENGINEER',  metadataJson:'{"file":"config/alert-thresholds.yml"}',   createdAt:'2026-06-27T09:00:00Z', updatedAt:'2026-07-09T11:30:00Z'},
  {id:'mig-001',          kind:'MIGRATION',  name:'V1__create_telemetry.sql', status:'VERIFIED',    provenance:'ENGINEER',  metadataJson:'{"file":"db/migration/V1__create_telemetry.sql"}', createdAt:'2026-06-26T08:00:00Z', updatedAt:'2026-07-08T14:00:00Z'},
  {id:'dep-kafka',        kind:'DEPENDENCY', name:'kafka-clients:3.7',        status:'PLANNED',     provenance:'ENGINEER',  metadataJson:'{}',                                       createdAt:'2026-06-27T09:00:00Z', updatedAt:'2026-06-27T09:00:00Z'},
  {id:'test-run-1',       kind:'TEST_RUN',   name:'CI run #48',               status:'VERIFIED',    provenance:'ENGINEER',  metadataJson:'{"passed":118,"failed":0}',                createdAt:'2026-07-08T13:55:00Z', updatedAt:'2026-07-12T16:45:00Z'}
] AS row
MERGE (n:DesignNode {projectId: 'beacon-demo@intent', id: row.id})
SET n += row, n.projectId = 'beacon-demo@intent';

// ---------- edges (35) ----------
UNWIND [
  // structure
  {id:'e-01', kind:'CONTAINS',     src:'sys-beacon',             dst:'cont-api'},
  {id:'e-02', kind:'CONTAINS',     src:'sys-beacon',             dst:'cont-worker'},
  {id:'e-03', kind:'CONTAINS',     src:'cont-api',               dst:'type-telemetry-service'},
  {id:'e-04', kind:'CONTAINS',     src:'cont-api',               dst:'type-alert-service'},
  {id:'e-05', kind:'CONTAINS',     src:'cont-api',               dst:'type-telemetry-record'},
  {id:'e-06', kind:'CONTAINS',     src:'cont-api',               dst:'type-alert'},
  {id:'e-07', kind:'CONTAINS',     src:'cont-worker',            dst:'type-audit-writer'},
  {id:'e-08', kind:'CONTAINS',     src:'type-telemetry-service', dst:'meth-ingest'},
  {id:'e-09', kind:'CONTAINS',     src:'type-alert-service',     dst:'meth-evaluate'},
  // contract surface
  {id:'e-10', kind:'EXPOSES',      src:'cont-api',               dst:'ep-post-telemetry'},
  {id:'e-11', kind:'EXPOSES',      src:'cont-api',               dst:'ep-get-alerts'},
  {id:'e-12', kind:'EXPOSES',      src:'cont-api',               dst:'ep-get-audit'},
  {id:'e-13', kind:'HAS_CONTRACT', src:'ep-post-telemetry',      dst:'contract-openapi'},
  {id:'e-14', kind:'HAS_CONTRACT', src:'ep-get-alerts',          dst:'contract-openapi'},
  // requirement coverage
  {id:'e-15', kind:'IMPLEMENTS',   src:'type-telemetry-service', dst:'req-1'},
  {id:'e-16', kind:'IMPLEMENTS',   src:'meth-ingest',            dst:'req-1'},
  {id:'e-17', kind:'IMPLEMENTS',   src:'ep-post-telemetry',      dst:'req-1'},
  {id:'e-18', kind:'IMPLEMENTS',   src:'type-alert-service',     dst:'req-2'},
  {id:'e-19', kind:'IMPLEMENTS',   src:'meth-evaluate',          dst:'req-2'},
  {id:'e-20', kind:'IMPLEMENTS',   src:'type-audit-writer',      dst:'req-3'},
  // data plane
  {id:'e-21', kind:'PERSISTS_TO',  src:'type-telemetry-record',  dst:'tbl-telemetry'},
  {id:'e-22', kind:'PERSISTS_TO',  src:'type-alert',             dst:'tbl-alerts'},
  {id:'e-23', kind:'WRITES',       src:'type-telemetry-service', dst:'tbl-telemetry'},
  {id:'e-24', kind:'READS',        src:'type-alert-service',     dst:'tbl-telemetry'},
  {id:'e-25', kind:'WRITES',       src:'type-alert-service',     dst:'tbl-alerts'},
  {id:'e-26', kind:'CONTAINS',     src:'tbl-telemetry',          dst:'col-t-id'},
  {id:'e-27', kind:'CONTAINS',     src:'tbl-telemetry',          dst:'col-t-device'},
  {id:'e-28', kind:'CONTAINS',     src:'tbl-telemetry',          dst:'col-t-ts'},
  {id:'e-29', kind:'CONTAINS',     src:'tbl-telemetry',          dst:'col-t-payload'},
  {id:'e-30', kind:'CONTAINS',     src:'tbl-alerts',             dst:'col-a-id'},
  {id:'e-31', kind:'CONTAINS',     src:'tbl-alerts',             dst:'col-a-rule'},
  {id:'e-32', kind:'CONTAINS',     src:'tbl-alerts',             dst:'col-a-raised'},
  // behaviour + dependencies (feeds blast_radius on type-telemetry-service)
  {id:'e-33', kind:'CALLS',        src:'type-alert-service',     dst:'type-telemetry-service'},
  {id:'e-34', kind:'DEPENDS_ON',   src:'type-audit-writer',      dst:'type-alert-service'},
  {id:'e-35', kind:'PUBLISHES',    src:'type-telemetry-service', dst:'topic-readings'},
  {id:'e-36', kind:'CONSUMES',     src:'cont-worker',            dst:'topic-readings'},
  {id:'e-37', kind:'USES_CONFIG',  src:'type-alert-service',     dst:'cfg-thresholds'},
  {id:'e-38', kind:'DEPENDS_ON',   src:'cont-api',               dst:'dep-kafka'},
  {id:'e-39', kind:'EVOLVES',      src:'mig-001',                dst:'tbl-telemetry'},
  {id:'e-40', kind:'TESTS',        src:'test-run-1',             dst:'type-telemetry-service'}
] AS row
MATCH (src:DesignNode {projectId: 'beacon-demo@intent', id: row.src})
MATCH (dst:DesignNode {projectId: 'beacon-demo@intent', id: row.dst})
MERGE (src)-[e:DESIGN_EDGE {projectId: 'beacon-demo@intent', id: row.id}]->(dst)
SET e.kind = row.kind, e.srcId = row.src, e.dstId = row.dst,
    e.provenance = 'ARCHITECT', e.version = '1',
    e.createdAt = '2026-06-26T09:00:00Z', e.updatedAt = '2026-07-09T11:30:00Z';
