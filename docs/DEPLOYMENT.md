# Deployment / 部署

## Local demo

```bash
semantic-hub serve --demo --db .semantic-hub/demo.db
```

Explicit demo mode grants admin access without authentication. Never expose it to an untrusted network. It seeds synthetic metadata only when the chosen database is empty. Do not reuse a demo database for confidential production metadata.

## Authenticated service

Without `HUB_DEMO=1` or `--demo`, the application refuses to start unless `HUB_TOKENS` is configured. Start with a separate database; it contains an empty catalog and can be populated by pasting `examples/commerce.yaml` into the editor, saving and publishing.

Generate three independent random tokens in your secret-management process (`python -c "import secrets; print(secrets.token_urlsafe(32))"`). Set `HUB_TOKENS` to this JSON structure, replacing all placeholders with 32+ character secrets:

```json
{
  "<admin-token>": {"name":"catalog-admin","role":"admin"},
  "<editor-token>": {"name":"analytics-editor","role":"editor"},
  "<viewer-token>": {"name":"agent-reader","role":"viewer"}
}
```

Environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `HUB_DB` | `.semantic-hub/hub.db` | SQLite metadata database |
| `HUB_TOKENS` | `{}` | Token → named principal/role mapping |
| `HUB_DEMO` | unset | `1` explicitly disables authentication |
| `HUB_ALLOW_DEMO_NETWORK` | unset | `1` allows non-loopback CLI binding in demo containers |
| `HUB_URL` | `http://127.0.0.1:8000` | MCP adapter's REST origin |
| `HUB_TOKEN` | empty | MCP adapter's bearer token |

Supply secrets through your deployment environment or secret manager. The application does **not** automatically load `.env`; Compose can read `.env` for interpolation. Token changes require a process restart. Tokens are not persisted in the database. Browser tokens exist only in tab memory and are cleared on reload. Do not use one shared admin token for every person.

Run the authenticated service behind your trusted gateway:

```bash
semantic-hub serve --host 127.0.0.1 --port 8000 --db /path/to/persistent/hub.db
```

For a container, use `compose.production.yaml` and set `HUB_TOKENS` in the invoking environment:

```bash
docker compose -f compose.production.yaml up --build -d
```

Both Compose examples bind only the host loopback port. Put your HTTPS reverse proxy in front of that port. The proxy should handle rate limiting, request timeouts and trusted host/routing policies. The hub's request-body cap is 1 MB. Bearer tokens require transport encryption outside a trusted local boundary. OpenAPI/schema UI assets are served publicly; business metadata endpoints require authorization. Swagger UI uses FastAPI's CDN assets; the product studio itself has no external scripts or fonts.

## Persistence, backup and recovery

SQLite uses WAL and local transactions. Use a local durable volume, not NFS/SMB and not a shared multi-replica filesystem. Metadata schema version is currently 1 (`PRAGMA user_version`). Future schema changes require explicit migrations before upgrade; v0.1 has no general migration engine.

A consistent online backup:

```python
import sqlite3
with sqlite3.connect('/path/to/hub.db') as source:
    with sqlite3.connect('/path/to/backup.db') as destination:
        source.backup(destination)
```

Keep backups encrypted and access-controlled because semantic metadata may itself be confidential. Restore while the service is stopped and verify the draft/published heads through `/api/history`. Restoring a semantic revision in the UI is different from database disaster recovery: it creates a new draft and preserves history.

## Production limits

This release has no SSO/OIDC, per-tenant/row/column ACL, credential vault, distributed storage, query execution, metrics exporter, remote MCP OAuth endpoint or automated data-quality scans. Metadata visibility is not a substitute for warehouse permissions. See [SECURITY.md](../SECURITY.md) and [ROADMAP.md](ROADMAP.md).
