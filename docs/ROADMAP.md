# Roadmap / 路线图

Statuses below distinguish implemented capabilities from proposals; no dates or delivery promises are implied.

| Stage | Status | Scope | Acceptance criteria |
| --- | --- | --- | --- |
| v0.1 runnable foundation | Implemented | Contract, studio, validation, snapshots, RBAC, compiler, lexical context, stdio MCP | Documented examples run; core/API/MCP regressions pass |
| v0.2 team workflow | Planned | Git round-trip, semantic diff, review approvals, UI i18n, pagination | A reviewed YAML change can be published with a reproducible commit/revision link |
| v0.3 warehouse confidence | Planned | Read-only metadata ingestion, uniqueness/data-quality checks, Hologres/Postgres/DuckDB conformance | Declared grains verified against test databases; dialect test matrix |
| v0.4 stronger semantics | Planned | Safe multi-hop planning, derived metrics, time grains, semi-additive inventory measures | No silent fanout; deterministic algebra and null/time semantics |
| v0.5 larger teams | Planned | PostgreSQL repository, migrations, OIDC, domain ACLs | Multi-user identity, policy tests, backup/migration drill |
| v0.6 retrieval ecosystem | Planned | Embeddings/reranking, evaluation set, versioned external adapters, MCP v2 migration | Measured retrieval quality and policy-equivalent API/MCP behavior |

## Priorities for a commerce analytics pilot / 电商试点

1. Pick 10–20 high-value metrics: seller GMV, valid orders, units sold, refund amount and inventory availability.
2. Map one curated order-item model and its shop dimension; explicitly test composite keys.
3. Agree currency and business-date rules before expanding platform coverage.
4. Build a bilingual evaluation set containing ambiguous requests, negative cases and expected metric IDs.
5. Compare compiled results to approved BI reports for the same filters and time range.
6. Expand to inventory only after snapshot/semi-additive time rules are executable, not just prose.

## Explicit non-goals for v0.1

- Replacing the warehouse, ETL scheduler, BI visualization engine or catalog lineage scanner.
- Claiming universal dbt/Cube/MetricFlow semantic interoperability.
- Arbitrary SQL execution, autonomous production writes or browser-managed warehouse credentials.
- Treating textual business rules as enforced authorization or numerical logic.
- Calling lexical retrieval “vector search” or claiming benchmark results without measured evidence.
