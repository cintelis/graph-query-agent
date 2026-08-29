"""Auditor Console — governed, deterministic, read-only questions over a
software DesignGraph stored in an external Neo4j.

Three parts:

* ``intents``  — the declarative registry of reviewed Cypher templates.
                 The registry IS the whole query surface; nothing else runs.
* ``executor`` — binds parameters and runs registry templates in a
                 READ-access session, stamping lineage on every response.
* ``router``   — the ``/api`` HTTP surface (projects, intents, ask, execute).

The target database belongs to another platform (the swarm-of-agents
DesignGraph); everything in this package is strictly read-only against it.
"""
