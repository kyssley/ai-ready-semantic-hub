"""REST boundary; all semantic reads are authorized and published by default."""

import hmac
import json
import os
from pathlib import Path
from typing import Literal
import yaml
from fastapi import Depends, FastAPI, HTTPException, Query as QueryParam, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import Field, ValidationError
from . import __version__
from .compiler import compile_query
from .models import Catalog, Query, StrictModel
from .retrieval import context, search
from .store import Conflict, Store
from .validation import validate_catalog, visible_catalog


class DraftInput(StrictModel):
    catalog: Catalog
    expected_revision: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=300)


class PublishInput(StrictModel):
    expected_revision: int = Field(ge=1)


class RestoreInput(PublishInput):
    revision: int = Field(ge=1)


class ContextInput(StrictModel):
    question: str = Field(min_length=1, max_length=1000)
    max_chars: int = Field(default=16000, ge=1000, le=100000)


class YamlInput(StrictModel):
    yaml: str = Field(max_length=900000)


def create_app(db_path=None, demo=None, tokens=None):
    demo = os.getenv("HUB_DEMO") == "1" if demo is None else demo
    tokens = json.loads(os.getenv("HUB_TOKENS", "{}")) if tokens is None else tokens
    if not isinstance(tokens, dict):
        raise ValueError("HUB_TOKENS must be a JSON object")
    if not demo and not tokens:
        raise ValueError("Set HUB_TOKENS or use explicit local demo mode (--demo)")
    for token, principal in tokens.items():
        if (
            len(token) < 32
            or not isinstance(principal, dict)
            or principal.get("role") not in ("viewer", "editor", "admin")
            or not principal.get("name")
        ):
            raise ValueError(
                "Each API token needs 32+ characters, a name, and viewer/editor/admin role"
            )
    store = Store(db_path or os.getenv("HUB_DB", ".semantic-hub/hub.db"))
    if demo:
        catalog = Catalog.model_validate(
            yaml.safe_load(Path(__file__).with_name("demo.yaml").read_text())
        )
    else:
        catalog = Catalog(name="Semantic Hub")
    store.seed(catalog)
    app = FastAPI(title="AI-Ready Semantic Hub", version=__version__)
    app.state.store = store
    bearer = HTTPBearer(auto_error=False)

    def principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if demo:
            return {"name": "local-demo", "role": "admin"}
        if credentials:
            for token, identity in tokens.items():
                if hmac.compare_digest(credentials.credentials.encode(), token.encode()):
                    return identity
        raise HTTPException(
            401, "Valid bearer token required", headers={"WWW-Authenticate": "Bearer"}
        )

    def editor(p=Depends(principal)):
        if p["role"] not in ("editor", "admin"):
            raise HTTPException(403, "Editor role required")
        return p

    def admin(p=Depends(principal)):
        if p["role"] != "admin":
            raise HTTPException(403, "Admin role required")
        return p

    def snapshot(p, channel="published", revision=None):
        result = store.read(channel, revision)
        result["catalog"] = visible_catalog(
            Catalog.model_validate(result["catalog"]), p["role"]
        ).model_dump()
        return result

    @app.middleware("http")
    async def safeguards(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 1_000_000:
                    return JSONResponse({"detail": "Request exceeds 1 MB"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
            )
        return response

    @app.exception_handler(Conflict)
    async def conflict(_req, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ValueError)
    async def value_error(_req, exc):
        detail = (
            exc.errors(include_context=False, include_input=False)
            if isinstance(exc, ValidationError)
            else str(exc)
        )
        return JSONResponse({"detail": detail}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(_req, exc):
        return JSONResponse({"detail": "Revision not found"}, status_code=404)

    @app.get("/healthz")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/session")
    def session(p=Depends(principal)):
        return {**p, "demo": demo}

    @app.get("/api/catalog")
    def read_catalog(channel: Literal["published", "draft"] = "published", p=Depends(principal)):
        if channel == "draft" and p["role"] == "viewer":
            raise HTTPException(403, "Drafts require editor role")
        return snapshot(p, channel)

    @app.get("/api/schema")
    def schema(_p=Depends(principal)):
        return Catalog.model_json_schema()

    @app.get("/api/export")
    def export(
        channel: Literal["published", "draft"] = "published",
        format: Literal["yaml", "json"] = "yaml",
        p=Depends(principal),
    ):
        result = read_catalog(channel, p)["catalog"]
        if format == "json":
            return result
        return Response(
            yaml.safe_dump(result, allow_unicode=True, sort_keys=False),
            media_type="application/yaml",
        )

    @app.post("/api/validate")
    def validate(catalog: Catalog, _p=Depends(editor)):
        errors = validate_catalog(catalog)
        return {"valid": not errors, "errors": errors}

    @app.post("/api/parse-yaml")
    def parse_yaml(body: YamlInput, _p=Depends(editor)):
        try:
            data = yaml.safe_load(body.yaml)
            catalog = Catalog.model_validate(data)
        except (yaml.YAMLError, RecursionError) as exc:
            raise ValueError("Invalid or recursive YAML") from exc
        return {"catalog": catalog.model_dump(), "errors": validate_catalog(catalog)}

    @app.put("/api/draft")
    def save(body: DraftInput, p=Depends(editor)):
        revision = store.save(body.catalog, body.expected_revision, p["name"], body.message)
        return {"revision": revision}

    @app.post("/api/publish")
    def publish(body: PublishInput, p=Depends(admin)):
        return {"revision": store.publish(body.expected_revision, p["name"])}

    @app.post("/api/restore")
    def restore(body: RestoreInput, p=Depends(editor)):
        old = store.read(revision=body.revision)
        rev = store.save(
            Catalog.model_validate(old["catalog"]),
            body.expected_revision,
            p["name"],
            f"Restore revision {body.revision} as new draft",
        )
        return {"revision": rev}

    @app.get("/api/history")
    def history(_p=Depends(editor)):
        return store.history()

    @app.get("/api/revisions/{revision}")
    def revision(revision: int, p=Depends(editor)):
        return snapshot(p, revision=revision)

    @app.get("/api/search")
    def search_api(
        q: str = QueryParam(min_length=1, max_length=1000),
        limit: int = QueryParam(default=10, ge=1, le=50),
        p=Depends(principal),
    ):
        s = snapshot(p)
        return {
            "revision": s["revision"],
            "results": search(Catalog.model_validate(s["catalog"]), q, limit),
        }

    @app.post("/api/context")
    def context_api(body: ContextInput, p=Depends(principal)):
        s = snapshot(p)
        return {
            "revision": s["revision"],
            "digest": s["digest"],
            **context(Catalog.model_validate(s["catalog"]), body.question, body.max_chars),
        }

    @app.get("/api/graph")
    def graph(p=Depends(principal)):
        s = snapshot(p)
        return {
            "revision": s["revision"],
            "nodes": s["catalog"]["models"],
            "edges": s["catalog"]["relationships"],
        }

    @app.post("/api/compile")
    def compile_api(body: Query, p=Depends(principal)):
        s = snapshot(p)
        return {
            "revision": s["revision"],
            "digest": s["digest"],
            **compile_query(Catalog.model_validate(s["catalog"]), body),
        }

    static = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(static / "index.html")

    return app
