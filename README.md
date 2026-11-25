<div align="center">

# AI-Ready Semantic Hub

**One versioned business language for BI and AI agents.**

[English](README.md) · [简体中文](README.zh-CN.md) · [Architecture](docs/ARCHITECTURE.md) · [Semantic specification](docs/SEMANTIC_SPEC.md) · [Contributing](CONTRIBUTING.md)

![Version](https://img.shields.io/badge/version-0.1.0-087f70)
![Python](https://img.shields.io/badge/python-3.11%2B-3670a0)
![License](https://img.shields.io/badge/license-MIT-blue)

</div>

A lightweight semantic control plane: define models, metrics, relationships and terminology once; validate and publish them; give BI developers and AI agents the same inspectable contract through a web studio, REST and MCP.

**v0.1 is a runnable reference implementation.** It is suitable for local evaluation and a small trusted team's pilot. It is not a distributed query engine, an autonomous text-to-SQL product or an enterprise identity platform. No LLM key or warehouse credentials are needed for the demo. All included examples are synthetic.

## Why this exists

An AI agent can discover a column named `amount` without knowing whether it means buyer payment, seller GMV or settlement revenue. A schema alone also cannot tell it which orders to exclude, which timezone defines a day, or whether a join multiplies rows.

Semantic Hub makes these decisions explicit and reviewable. Its primary unit is a **versioned semantic contract**, not a chat session. Generated SQL and retrieved context carry the published revision and content hash.

| Concern | Implemented in v0.1 |
| --- | --- |
| Model identity | Physical relation, typed columns, owner and composite primary key |
| Metrics | Sum, count, distinct count, average, min, max, ratio of sums, fixed filters |
| Relationships | Composite keys and cardinality; direct to-one joins in the compiler |
| Business meaning | Descriptions, bilingual synonyms, rules, tags and terms |
| Governance | Validated drafts, admin publication, immutable snapshots, restore-as-draft, audit history |
| AI consumption | Explainable English/Chinese lexical search, complete context packages, three MCP tools |
| Query safety | Identifier allowlist, bound values, currency guard, fanout/ambiguity rejection |
| Access | Viewer/editor/admin bearer tokens; public/internal entity visibility |
| Portability | YAML/JSON import/export, generated JSON Schema, conservative dbt manifest import |
| Developer experience | Web studio, CLI, OpenAPI, Docker Compose, tests and GitHub Actions |

## Run in two minutes

Requires Python 3.11+ (tested locally with 3.12). From the repository root:

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -e ".[mcp]"
semantic-hub serve --demo
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). OpenAPI is at `/docs`.

Demo mode is explicitly unauthenticated and grants local admin access. The CLI binds to loopback by default. The demo initializes a new database with three commerce models, four metrics, one composite relationship and two terms. Restarting never overwrites saved data. To reset, stop the server and start with another `--db` path.

For the checked-in dependency resolution, install [uv](https://docs.astral.sh/uv/) and run:

```bash
uv sync --frozen --extra mcp --extra dev
uv run semantic-hub serve --demo
```

Docker alternative:

```bash
docker compose up --build
```

Compose binds the host port to `127.0.0.1`, uses a named data volume, and runs the container as a non-root user. See [deployment](docs/DEPLOYMENT.md) before enabling authenticated network access.

## Try the full workflow

1. **Catalog**: search `GMV` or `成交额`, then inspect the metric's calculation and business rules.
2. **Relationships**: inspect the two-column `platform + shop_id` join. A shop ID alone is not globally unique.
3. **Query playground**: use the commerce example and compile. Inspect parameter values and lineage separately from SQL.
4. **Definition editor**: edit YAML, validate, describe the change and save a draft. Consumers still see the published version.
5. **Publish**: an admin explicitly promotes that revision. Old revisions remain immutable.
6. **Agent context**: ask `按地区统计商家折后 GMV`; inspect definitions, join contracts and the revision hash returned to an agent.
7. **History**: restore an old revision as a new draft, review it, then publish if appropriate.

The UI is English-first; definitions, search and documentation support Chinese. Full UI localization is planned.

## Semantic definition

A metric references typed columns; arbitrary executable SQL is not accepted:

```yaml
id: seller_gmv
label: Seller GMV / 商家折后 GMV
owner: commerce-analytics
model: order_items
aggregation: sum
column: seller_net_amount
unit: currency
currency_dimension: order_items.currency
time_dimension: order_items.order_date
filters:
  - {field: order_items.status, op: ne, value: cancelled}
  - {field: order_items.is_sample, op: eq, value: false}
business_rules:
  - Exclude shipping and tax; group by currency or filter one currency.
```

This is an excerpt; [examples/commerce.yaml](examples/commerce.yaml) is the complete, validated catalog. `business_rules` are descriptive context. Only structured fields such as `filters` and `currency_dimension` affect compiled SQL. The hub cannot verify the warehouse's physical data grain or timezone normalization.

```bash
semantic-hub validate examples/commerce.yaml
semantic-hub schema > catalog.schema.json
semantic-hub import-dbt manifest.json > imported.yaml
```

The dbt importer requires explicit column metadata and `meta.semantic_hub.primary_key`; it emits warnings for skipped models and never invents metrics or relationships. See [integrations](docs/INTEGRATIONS.md).

## REST and SQL compilation

For demo mode, omit authorization. For authenticated mode, add `Authorization: Bearer <token>`.

```bash
curl -X POST http://127.0.0.1:8000/api/compile \
  -H 'Content-Type: application/json' \
  --data-binary @examples/query.json
```

The response contains `sql`, `parameters`, `lineage`, `dialect`, `revision`, `digest` and `warnings`. Values use psycopg-style named parameters for PostgreSQL/Hologres and `$name` parameters for DuckDB. Supply SQL and its parameter map separately to your execution layer. **The hub does not execute warehouse SQL.**

Hologres is a PostgreSQL-compatible compilation target; no live Hologres/PostgreSQL integration or performance certification is claimed. Cross-fact queries, multi-hop joins, arbitrary formulas, FX conversion and time-grain transformations are deliberately rejected or absent in this release.

## MCP integration

Install the `mcp` extra and keep the API running. Configure a stdio-capable MCP client:

```json
{
  "mcpServers": {
    "semantic-hub": {
      "command": "/absolute/path/to/.venv/bin/semantic-hub",
      "args": ["mcp"],
      "env": {
        "HUB_URL": "http://127.0.0.1:8000",
        "HUB_TOKEN": "your-viewer-token"
      }
    }
  }
}
```

On Windows use the full path to `.venv\\Scripts\\semantic-hub.exe`. Omit `HUB_TOKEN` for local demo mode. Real tokens belong in the client's secret store or process environment, not in committed configuration.

| Tool | Purpose |
| --- | --- |
| `search_semantics` | Find published models, metrics and terms |
| `get_semantic_context` | Return permission-filtered definitions and direct join context |
| `compile_metric_query` | Compile a structured metric request to parameterized SQL |

The adapter uses the official SDK's maintained **v1 line**, explicitly pinned to `mcp>=1.28,<2`. It provides stdio transport only and delegates authorization to the REST API. No mutation tools or SQL execution tools are exposed. [MCP SDK v1 documentation](https://py.sdk.modelcontextprotocol.io/v1/).

## Repository map

| Path | Responsibility |
| --- | --- |
| `src/semantic_hub/models.py` | Typed public contract and JSON Schema |
| `validation.py` | Reference, type, key and visibility validation |
| `compiler.py` | Deterministic constrained SQL compiler |
| `retrieval.py` | Bilingual lexical ranking and context assembly |
| `store.py` | Transactional SQLite revisions and audit log |
| `api.py` | REST, authorization and web studio delivery |
| `mcp_server.py` | Read-only MCP-to-REST adapter |
| `importers.py`, `cli.py` | Portable metadata import and developer commands |
| `static/` | Build-free, responsive web studio |
| `tests/`, `scripts/browser_smoke.py` | Core, REST, MCP and browser workflows |
| `docs/` | Architecture, specification, deployment, integration and roadmap |

## Development

```bash
python -m pip install -e ".[dev,mcp]"
python -m unittest discover -s tests -v
ruff check src tests scripts
ruff format --check src tests scripts
python -m build
```

The MCP test starts a disposable HTTP server and verifies a real stdio client handshake, tool discovery, calls and access denial. SQL semantic tests execute the common SQL subset on SQLite with adapted placeholders. They do not replace warehouse compatibility tests.

Optional browser test, using a disposable demo database:

```bash
python -m playwright install chromium
semantic-hub serve --demo --db .semantic-hub/browser-test.db
# In another shell, using the same virtual environment:
python scripts/browser_smoke.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), [ROADMAP.md](docs/ROADMAP.md) and [CHANGELOG.md](CHANGELOG.md). MIT licensed. No external analytics, hosted inference service or proprietary runtime is required.

Local check results: [VALIDATION.md](docs/VALIDATION.md). To publish this source to your account: [PUBLISHING.md](docs/PUBLISHING.md).
