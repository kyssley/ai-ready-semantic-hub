"""The portable semantic contract. No executable SQL or credentials in definitions."""

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")]
Reference = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,62}\.[a-z][a-z0-9_]{0,62}$")]
Text = Annotated[str, Field(max_length=4000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Column(StrictModel):
    name: Identifier
    label: Text = ""
    data_type: Literal["string", "integer", "number", "date", "timestamp", "boolean"]
    description: Text = ""
    dimension: bool = True


class Entity(StrictModel):
    id: Identifier
    label: Annotated[str, Field(min_length=1, max_length=160)]
    description: Text = ""
    owner: Annotated[str, Field(min_length=1, max_length=160)]
    tags: list[Identifier] = Field(default_factory=list, max_length=30)
    synonyms: list[Annotated[str, Field(max_length=160)]] = Field(
        default_factory=list, max_length=30
    )
    visibility: Literal["public", "internal"] = "public"


class Model(Entity):
    table: Annotated[
        str, Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){0,2}$", max_length=190)
    ]
    primary_key: list[Identifier] = Field(min_length=1, max_length=10)
    columns: list[Column] = Field(min_length=1, max_length=200)


class Relationship(StrictModel):
    id: Identifier
    from_model: Identifier
    to_model: Identifier
    from_columns: list[Identifier] = Field(min_length=1, max_length=10)
    to_columns: list[Identifier] = Field(min_length=1, max_length=10)
    cardinality: Literal["many_to_one", "one_to_one", "one_to_many", "many_to_many"]
    description: Text = ""


class Filter(StrictModel):
    field: Reference
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "is_null", "not_null"] = "eq"
    value: str | int | float | bool | list[str | int | float | bool] | None = None

    @model_validator(mode="after")
    def shape(self):
        if self.op == "in":
            if not isinstance(self.value, list) or not 1 <= len(self.value) <= 100:
                raise ValueError("in requires 1..100 scalar values")
        elif self.op in ("is_null", "not_null"):
            if self.value is not None:
                raise ValueError("null operators do not take a value")
        elif self.value is None or isinstance(self.value, list):
            raise ValueError("comparison requires a non-null scalar value")
        if isinstance(self.value, str) and len(self.value) > 2000:
            raise ValueError("filter value too long")
        return self


class Metric(Entity):
    model: Identifier
    aggregation: Literal["sum", "count", "count_distinct", "avg", "min", "max", "ratio"]
    column: Identifier | None = None
    denominator: Identifier | None = None
    unit: Annotated[str, Field(max_length=80)] = "number"
    currency_dimension: Reference | None = None
    time_dimension: Reference | None = None
    filters: list[Filter] = Field(default_factory=list, max_length=20)
    business_rules: list[Text] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def shape(self):
        if self.aggregation != "count" and self.column is None:
            raise ValueError("column is required for this aggregation")
        if (self.aggregation == "ratio") != (self.denominator is not None):
            raise ValueError("denominator is required only for ratio")
        return self


class Term(Entity):
    metric_ids: list[Identifier] = Field(default_factory=list, max_length=50)


class Catalog(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    name: Annotated[str, Field(min_length=1, max_length=160)]
    models: list[Model] = Field(default_factory=list, max_length=200)
    relationships: list[Relationship] = Field(default_factory=list, max_length=500)
    metrics: list[Metric] = Field(default_factory=list, max_length=500)
    terms: list[Term] = Field(default_factory=list, max_length=500)


class Query(StrictModel):
    metrics: list[Identifier] = Field(min_length=1, max_length=20)
    dimensions: list[Reference] = Field(default_factory=list, max_length=20)
    filters: list[Filter] = Field(default_factory=list, max_length=30)
    limit: int = Field(default=100, ge=1, le=10000)
    dialect: Literal["postgres", "hologres", "duckdb"] = "postgres"
