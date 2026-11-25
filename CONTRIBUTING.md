# Contributing / 参与贡献

English and Chinese issues and pull requests are welcome. 欢迎中文与英文反馈。

1. Describe a reproducible problem and expected semantic behavior; remove credentials and private data.
2. For architecture/schema changes, open a design discussion before introducing dependencies or broad abstractions.
3. Keep code under `src/semantic_hub`; add regression tests for semantic and permission changes.
4. Update both README files when user-facing behavior changes. Regenerate `docs/catalog.schema.json` for contract changes.
5. Run the checks below. Use a small PR explaining the problem, behavior and validation evidence.

```bash
uv sync --frozen --extra dev --extra mcp
uv run python -m unittest discover -s tests -v
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run semantic-hub validate examples/commerce.yaml
uv run python -m build
```

Update dependencies intentionally with `uv lock`, then regenerate the Docker runtime lock with `uv export --frozen --extra mcp --no-dev --no-emit-project -o requirements.lock`. Do not commit `.env`, database files, real customer examples or generated build outputs.

A metric contribution must define: grain, aggregation, time meaning, currency behavior, exclusions, NULL/zero behavior and owner. Prose rules that affect a number need a corresponding executable representation or an explicit limitation.

For SQL changes, test results against synthetic rows, not just expected SQL strings. Include ambiguous-join and unauthorized-access negative cases. Avoid inventing unverified warehouse compatibility claims.

Project governance: maintainer review is required for merges; backward-incompatible contract changes require a schema version and migration proposal. No CLA is required; contributions are accepted under the MIT license. Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
