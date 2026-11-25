"""Deterministic SELECT compiler. Values are parameters; SQL fragments are never input."""

from .models import Catalog, Query
from .validation import check_filter_value, require_valid


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def compile_query(catalog: Catalog, query: Query) -> dict:
    require_valid(catalog)
    models = {m.id: m for m in catalog.models}
    metrics = {m.id: m for m in catalog.metrics}
    if len(set(query.metrics)) != len(query.metrics) or len(set(query.dimensions)) != len(
        query.dimensions
    ):
        raise ValueError("Duplicate metrics or dimensions")
    if any(mid not in metrics for mid in query.metrics):
        raise ValueError("Unknown or unavailable metric")
    chosen = [metrics[mid] for mid in query.metrics]
    if len({m.model for m in chosen}) != 1:
        raise ValueError("Cross-fact queries are not supported; use one metric model")
    base = chosen[0].model
    referenced = {base}
    params = {}

    def field(ref, require_dimension=False):
        model, name = ref.split(".")
        if model not in models:
            raise ValueError(f"Unknown or unavailable model: {model}")
        column = next((c for c in models[model].columns if c.name == name), None)
        if column is None or (require_dimension and not column.dimension):
            raise ValueError(f"Unknown or unavailable dimension: {ref}")
        referenced.add(model)
        return f"{quote(model)}.{quote(name)}", column

    def parameter(value):
        name = f"p{len(params)}"
        params[name] = value
        return f"%({name})s" if query.dialect != "duckdb" else f"${name}"

    def predicate(f, dimension=True):
        expr, col = field(f.field, dimension)
        if f.op in ("is_null", "not_null"):
            return expr + (" IS NULL" if f.op == "is_null" else " IS NOT NULL")
        if f.op == "in":
            for v in f.value:
                check_filter_value(col, v)
            return f"{expr} IN ({', '.join(parameter(v) for v in f.value)})"
        check_filter_value(col, f.value)
        op = {"eq": "=", "ne": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[f.op]
        return f"{expr} {op} {parameter(f.value)}"

    selections = []
    groups = []
    for ref in query.dimensions:
        expr, _ = field(ref, True)
        groups.append(expr)
        selections.append(f"{expr} AS {quote(ref.replace('.', '__'))}")
    for m in chosen:
        if m.currency_dimension and m.currency_dimension not in query.dimensions:
            fixed = any(
                f.field == m.currency_dimension
                and (f.op == "eq" or (f.op == "in" and len(f.value) == 1))
                for f in [*query.filters, *m.filters]
            )
            if not fixed:
                raise ValueError(
                    f"{m.id}: group by {m.currency_dimension} or filter to one currency"
                )
        cond = " AND ".join(predicate(f, False) for f in m.filters)

        def value(col):
            expr = field(f"{base}.{col}")[0] if col else "1"
            return f"CASE WHEN {cond} THEN {expr} END" if cond else expr

        val = value(m.column)
        if m.aggregation == "ratio":
            expr = f"(1.0 * SUM({val}) / NULLIF(SUM({value(m.denominator)}), 0))"
        elif m.aggregation == "count_distinct":
            expr = f"COUNT(DISTINCT {val})"
        else:
            expr = f"{m.aggregation.upper()}({val})"
        selections.append(f"{expr} AS {quote(m.id)}")
    predicates = [predicate(f) for f in query.filters]
    joins = []
    used = []
    # Deliberately one hop: ambiguity and fanout fail closed rather than guess a route.
    for target in sorted(referenced - {base}):
        candidates = [
            r
            for r in catalog.relationships
            if r.from_model == base
            and r.to_model == target
            and r.cardinality in ("many_to_one", "one_to_one")
        ]
        if len(candidates) != 1:
            raise ValueError(f"Need exactly one direct to-one relationship from {base} to {target}")
        r = candidates[0]
        condition = " AND ".join(
            f"{quote(base)}.{quote(a)} = {quote(target)}.{quote(b)}"
            for a, b in zip(r.from_columns, r.to_columns)
        )
        table = ".".join(quote(s) for s in models[target].table.split("."))
        joins.append(f"LEFT JOIN {table} AS {quote(target)} ON {condition}")
        used.append(r.id)
    table = ".".join(quote(s) for s in models[base].table.split("."))
    sql = "SELECT\n  " + ",\n  ".join(selections) + f"\nFROM {table} AS {quote(base)}"
    if joins:
        sql += "\n" + "\n".join(joins)
    if predicates:
        sql += "\nWHERE " + " AND ".join(predicates)
    if groups:
        sql += "\nGROUP BY " + ", ".join(groups) + "\nORDER BY " + ", ".join(groups)
    sql += f"\nLIMIT {query.limit}"
    return {
        "sql": sql,
        "parameters": params,
        "dialect": query.dialect,
        "lineage": {"models": sorted(referenced), "metrics": query.metrics, "relationships": used},
        "warnings": [
            "Compilation only; no warehouse query was executed.",
            "Join uniqueness is declared metadata; verify it in the warehouse.",
        ],
    }
