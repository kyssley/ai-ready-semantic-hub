# Validation evidence / 验证记录

Validation date: 2026-11-25. This report distinguishes completed local checks from supplied CI definitions that have not run on a remote repository.

| Check | Local result |
| --- | --- |
| Python contract/compiler/retrieval/store/REST suite | 56 tests passed |
| Real MCP stdio client + HTTP service | 1 test passed (discovery, search, context, compilation, permission denial) |
| Total Python tests | 57 passed |
| Locked dependency installation | `uv sync --frozen --extra dev --extra mcp` succeeded on Python 3.12.14 |
| Ruff lint and formatting | Passed |
| JavaScript syntax | Passed |
| Synthetic catalog validation and JSON Schema generation | Passed |
| Python source distribution and wheel build | Passed |
| Browser workflow | Passed with local headless Chromium: catalog, graph, SQL compile, context, validate/save/publish, restore, mobile-width overflow check |
| Hologres / PostgreSQL live execution | Not performed; no warehouse credentials used |
| Docker image build/run | Not performed locally; Docker is unavailable in this execution environment |
| GitHub Actions | Configuration supplied; remote runs require a created/pushed repository |

The browser CDN download was unavailable in this environment. A Chromium binary from the published `@sparticuz/chromium` npm package was used for local verification; it is a test-environment dependency only and is not bundled into the project. Standard CI installs Playwright Chromium. Set `CHROMIUM_EXECUTABLE` to use an existing compatible binary for `scripts/browser_smoke.py`.

Compiler result tests execute the common SQL subset on SQLite with parameter markers adapted. Cases verify composite joins across repeated shop IDs on different platforms, exclusion of cancelled/sample orders, distinct order counting, ratio-of-sums and zero denominator behavior. They validate semantic outcomes but do not certify target-database behavior or performance.

There are no measured latency/throughput claims. This version remains a small-team pilot implementation with the documented limits in [ARCHITECTURE.md](ARCHITECTURE.md) and [SECURITY.md](../SECURITY.md).
