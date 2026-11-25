"""Conservative dbt manifest import. Never infers business metrics or primary keys."""

import re
from .models import Catalog, Model, Column


def import_dbt(manifest: dict) -> tuple[Catalog, list[str]]:
    models = []
    warnings = []
    for node in manifest.get("nodes", {}).values():
        if node.get("resource_type") not in ("model", "seed"):
            continue
        name = node.get("name", "")
        meta = node.get("meta", {}) or node.get("config", {}).get("meta", {})
        hub = meta.get("semantic_hub", {})
        primary_key = hub.get("primary_key")
        raw_columns = node.get("columns", {})
        if not primary_key or not raw_columns:
            warnings.append(f"Skipped {name}: declare columns and meta.semantic_hub.primary_key")
            continue
        cols = []
        for col in raw_columns.values():
            dtype = str(col.get("data_type", "")).lower()
            if re.search(r"int", dtype):
                dtype = "integer"
            elif re.search(r"numeric|decimal|float|double|real", dtype):
                dtype = "number"
            elif "timestamp" in dtype:
                dtype = "timestamp"
            elif dtype == "date":
                dtype = "date"
            elif "bool" in dtype:
                dtype = "boolean"
            else:
                if not dtype:
                    warnings.append(f"{name}.{col['name']}: missing type, imported as string")
                dtype = "string"
            cols.append(
                Column(name=col["name"], data_type=dtype, description=col.get("description", ""))
            )
        model = Model(
            id=name,
            label=name,
            description=node.get("description", ""),
            owner=hub.get("owner", "unassigned"),
            table=".".join(x for x in [node.get("schema"), node.get("alias", name)] if x),
            primary_key=primary_key,
            columns=cols,
        )
        models.append(model)
    return Catalog(name="Imported dbt catalog", models=models), warnings
