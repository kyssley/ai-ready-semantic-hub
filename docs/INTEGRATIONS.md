# Integrations / 集成设计

## Hologres / PostgreSQL

v0.1 compiles quoted PostgreSQL-family identifiers and named parameters. The `hologres` target currently uses the same deliberately small syntax subset as `postgres`: SELECT, aggregate CASE, LEFT JOIN, WHERE, GROUP BY, ORDER BY, LIMIT, NULLIF. It does not assume version-specific UDFs, LATERAL, dynamic tables or unsupported timestamp precision.

Keep normalized business dates, currency and order keys in trusted warehouse views. In a cross-platform order model, an order key must include the required platform/store scope or use a collision-free surrogate. The synthetic example documents this requirement but does not construct production keys.

An external executor should:

1. Authenticate the business user and authorize the selected datasets independently.
2. Obtain SQL + parameters from the hub's published compiler response.
3. Connect with a least-privilege read-only account.
4. Bind values using its driver; enforce timeouts, resource budgets and result caps.
5. Log caller identity, semantic revision and warehouse query ID.

Do not interpolate `parameters` into SQL manually. The hub has no database connection endpoint or live introspection in v0.1. It does not grant users access to Hologres.

## FineBI / Power BI / custom dashboards

Use exported semantic definitions as the reviewable source for dashboard logic, or have a custom service compile supported metric requests. Existing dashboards do not automatically begin using this hub: calculations must be aligned or adapters written. No native FineBI/Power BI plugin is claimed. Existing BI licensing, user authorization and row-level security continue to apply.

## DataWorks / GitLab / GitHub

Store reviewed catalog YAML in your code repository. Run `semantic-hub validate catalog.yaml` in CI. An authorized deployment step can read the current draft revision, PUT a draft and POST publication. A `409` should stop automation for human reconciliation; do not silently overwrite newer edits.

v0.1 does not watch Git or push UI edits back automatically. YAML export is the bridge between the UI and Git review. Avoid maintaining two authoritative copies without a documented release procedure.

## dbt manifest import

The CLI imports only model/seed metadata with an explicit primary key:

```yaml
models:
  - name: orders
    config:
      meta:
        semantic_hub:
          primary_key: [platform, shop_id, order_id]
          owner: commerce-analytics
    columns:
      - {name: platform, data_type: text}
      - {name: shop_id, data_type: text}
      - {name: order_id, data_type: text}
```

Compile dbt to generate `manifest.json`, then:

```bash
semantic-hub import-dbt target/manifest.json > imported.yaml
semantic-hub validate imported.yaml
```

The importer uses schema + alias (database is intentionally omitted for PostgreSQL-style bindings), maps common types, warns about absent types, and skips models without explicit key/column metadata. Review the output: complex/unknown database types fall back to string, and contracts using unsupported identifier forms are rejected. It does not import dbt Semantic Layer/MetricFlow metrics, infer relationships, process source nodes or preserve arbitrary SQL transformations.

## Agent usage sequence

1. `search_semantics`: discover candidate metrics and inspect names; ask the user when meaning is ambiguous.
2. `get_semantic_context`: retrieve rules, grain and relationships for a focused question.
3. Construct the supported structured query with explicit date/currency choices.
4. `compile_metric_query`: obtain inspectable SQL and revision; do not describe it as a result dataset.
5. If execution is needed, send to an independently authorized query service.

An agent's natural-language reasoning can still be wrong. Treat catalog descriptions as untrusted content, require application-side tool policies, and keep publication rights separate from agent-reader rights. No LLM vendor dependency is imposed.
