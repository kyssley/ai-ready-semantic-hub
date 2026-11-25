import argparse
import json
import os
from pathlib import Path
import sys
import yaml
from .models import Catalog
from .validation import validate_catalog


def main():
    parser = argparse.ArgumentParser(description="AI-Ready Semantic Hub")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Start API and web studio")
    serve.add_argument("--demo", action="store_true", help="Local unauthenticated synthetic demo")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--db", default=None)
    validate = sub.add_parser("validate", help="Validate portable YAML or JSON")
    validate.add_argument("file", type=Path)
    sub.add_parser("schema", help="Print JSON Schema")
    sub.add_parser("mcp", help="Start read-only stdio MCP adapter")
    imp = sub.add_parser("import-dbt", help="Import explicit dbt model metadata to YAML")
    imp.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            import uvicorn
            from .api import create_app

            if (
                (args.demo or os.getenv("HUB_DEMO") == "1")
                and args.host not in ("127.0.0.1", "localhost", "::1")
                and os.getenv("HUB_ALLOW_DEMO_NETWORK") != "1"
            ):
                parser.error(
                    "Demo network binding requires HUB_ALLOW_DEMO_NETWORK=1; keep the port private"
                )
            uvicorn.run(
                create_app(db_path=args.db, demo=args.demo or None), host=args.host, port=args.port
            )
        elif args.command == "validate":
            catalog = Catalog.model_validate(yaml.safe_load(args.file.read_text(encoding="utf-8")))
            errors = validate_catalog(catalog)
            print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
            return 1 if errors else 0
        elif args.command == "schema":
            print(json.dumps(Catalog.model_json_schema(), indent=2))
        elif args.command == "mcp":
            from .mcp_server import main as run_mcp

            run_mcp()
        elif args.command == "import-dbt":
            from .importers import import_dbt

            catalog, warnings = import_dbt(json.loads(args.file.read_text(encoding="utf-8")))
            errors = validate_catalog(catalog)
            if errors:
                raise ValueError(errors)
            print(yaml.safe_dump(catalog.model_dump(), allow_unicode=True, sort_keys=False))
            for warning in warnings:
                print(warning, file=sys.stderr)
        return 0
    except (ValueError, OSError, yaml.YAMLError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
