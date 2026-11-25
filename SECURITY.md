# Security policy / 安全说明

v0.1 is a pilot implementation. Only the current development line receives fixes; there is no enterprise security certification or long-term support commitment.

## Reporting

Do not post working secrets, private data or exploitable details in public issues. Use the repository's GitHub private vulnerability reporting channel if enabled by the maintainer. If it is not enabled, open a minimal issue requesting a private contact without disclosing the vulnerability. Maintainers should enable private reporting before public launch.

## Boundaries

- Production mode requires random 32+ character bearer tokens; demo mode is explicitly unauthenticated.
- Role policy is catalog-wide. `public` entities remain authentication-protected; `internal` entities are hidden from viewers across all API and MCP reads.
- There is no multi-tenant isolation, row/column ACL, SSO, token expiry or dynamic revocation service. Restart the process to rotate tokens.
- The hub never stores warehouse credentials or executes SQL. Generated SQL still requires independently authorized execution and operational limits.
- Fixed filters are business logic, not a mandatory security policy. Descriptive rules are not executable protections.
- Metadata is potentially sensitive; protect the database, backups and editor tokens. Editors can read all internal metadata and author text consumed by agents.
- Descriptions can contain prompt injection. Treat context as data; constrain downstream tool use and never let retrieved prose override application policy.
- SQL identifiers are constrained and quoted; filter values are bound parameters. Do not concatenate parameters into SQL in downstream code.
- Local MCP calls bypass ambient HTTP proxies for loopback origins; remote origins retain standard environment proxy/TLS behavior.
- A 1 MB body limit and finite catalog/query sizes bound routine inputs. Public-facing deployments still need HTTPS, gateway limits and monitoring.
- SQL LIMIT caps result rows, not scan cost. Join uniqueness is an assertion until independently verified against data.
- Local audit records share mutation transactions but are not tamper-proof against filesystem administrators.

## Deployment defaults

Docker runs as a non-root user. Both Compose variants publish to host loopback only. The authenticated variant requires `HUB_TOKENS` and uses a separate volume. The studio sets a strict same-origin script policy, does not use external scripts/fonts, and keeps the bearer token only in tab memory. OpenAPI documentation is public and FastAPI's Swagger UI may load CDN assets; business metadata remains protected.
