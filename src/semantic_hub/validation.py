"""Cross-reference and grain validation shared by every write and compiler."""

from datetime import date, datetime

from .models import Catalog, Column


def check_filter_value(column: Column, value):
    dtype = column.data_type
    if dtype in ("integer", "number"):
        if type(value) not in (int, float) or (dtype == "integer" and type(value) is not int):
            raise ValueError(f"Expected {dtype} filter value")
    elif dtype == "boolean" and type(value) is not bool:
        raise ValueError("Expected boolean filter value")
    elif dtype in ("string", "date", "timestamp"):
        if not isinstance(value, str):
            raise ValueError(f"Expected {dtype} string")
        if dtype == "date":
            date.fromisoformat(value)
        if dtype == "timestamp":
            datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_catalog(catalog: Catalog) -> list[dict]:
    errors = []

    def error(path, message):
        errors.append({"path": path, "message": message})

    for kind in ("models", "relationships", "metrics", "terms"):
        ids = [x.id for x in getattr(catalog, kind)]
        if len(ids) != len(set(ids)):
            error(kind, "Duplicate IDs")
    models = {m.id: m for m in catalog.models}
    columns = {m.id: {c.name: c for c in m.columns} for m in catalog.models}

    def reference(ref, path):
        model, col = ref.split(".")
        if model not in columns or col not in columns[model]:
            error(path, f"Unknown field: {ref}")
            return None
        return columns[model][col]

    for m in catalog.models:
        if len(m.columns) != len(columns[m.id]):
            error(f"models.{m.id}", "Duplicate column names")
        if len(m.primary_key) != len(set(m.primary_key)):
            error(f"models.{m.id}", "Duplicate primary key columns")
        for key in m.primary_key:
            reference(f"{m.id}.{key}", f"models.{m.id}.primary_key")
    for r in catalog.relationships:
        path = f"relationships.{r.id}"
        if r.from_model == r.to_model:
            error(path, "Self joins are not supported in v1")
        if len(r.from_columns) != len(r.to_columns):
            error(path, "Join key lengths differ")
        for model, cols in [(r.from_model, r.from_columns), (r.to_model, r.to_columns)]:
            if len(cols) != len(set(cols)):
                error(path, "Duplicate join key columns")
            for col in cols:
                reference(f"{model}.{col}", path)
        for left, right in zip(r.from_columns, r.to_columns):
            a = columns.get(r.from_model, {}).get(left)
            b = columns.get(r.to_model, {}).get(right)
            if a and b and a.data_type != b.data_type:
                error(path, "Join key types differ")
        if r.cardinality in ("many_to_one", "one_to_one") and r.to_model in models:
            if set(r.to_columns) != set(models[r.to_model].primary_key):
                error(path, "To-one target must join the complete declared primary key")
        if r.cardinality == "one_to_one" and r.from_model in models:
            if set(r.from_columns) != set(models[r.from_model].primary_key):
                error(path, "One-to-one source must join the complete declared primary key")
    metrics = {m.id: m for m in catalog.metrics}
    for m in catalog.metrics:
        path = f"metrics.{m.id}"
        if m.model not in models:
            error(path, f"Unknown model: {m.model}")
            continue
        if m.visibility == "public" and models[m.model].visibility == "internal":
            error(path, "Public metric cannot reference an internal model")
        for col in [m.column, m.denominator]:
            if col:
                c = reference(f"{m.model}.{col}", path)
                if (
                    c
                    and m.aggregation in ("sum", "avg", "ratio")
                    and c.data_type not in ("number", "integer")
                ):
                    error(path, "Numeric aggregation requires numeric columns")
        for ref in [m.time_dimension, m.currency_dimension]:
            if ref:
                c = reference(ref, path)
                if not ref.startswith(m.model + ".") or (c and not c.dimension):
                    error(path, "Time/currency dimension must be a dimension of the metric model")
                if ref == m.time_dimension and c and c.data_type not in ("date", "timestamp"):
                    error(path, "Time dimension must have date or timestamp type")
        for f in m.filters:
            c = reference(f.field, path)
            if c and f.op not in ("is_null", "not_null"):
                try:
                    for v in f.value if isinstance(f.value, list) else [f.value]:
                        check_filter_value(c, v)
                except ValueError as exc:
                    error(path, str(exc))
            if not f.field.startswith(m.model + "."):
                error(path, "Metric filters must use the metric's own model")
    for t in catalog.terms:
        for mid in t.metric_ids:
            if mid not in metrics:
                error(f"terms.{t.id}", f"Unknown metric: {mid}")
            elif t.visibility == "public" and metrics[mid].visibility == "internal":
                error(f"terms.{t.id}", "Public term cannot reference an internal metric")
    return errors


def require_valid(catalog: Catalog) -> Catalog:
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError(errors)
    return catalog


def visible_catalog(catalog: Catalog, role: str) -> Catalog:
    if role in ("editor", "admin"):
        return catalog
    data = catalog.model_dump()
    for kind in ("models", "metrics", "terms"):
        data[kind] = [x for x in data[kind] if x["visibility"] == "public"]
    model_ids = {x["id"] for x in data["models"]}
    data["relationships"] = [
        r
        for r in data["relationships"]
        if r["from_model"] in model_ids and r["to_model"] in model_ids
    ]
    return Catalog.model_validate(data)
