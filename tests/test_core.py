import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import yaml
from pydantic import ValidationError
from semantic_hub.compiler import compile_query
from semantic_hub.importers import import_dbt
from semantic_hub.models import Catalog, Query
from semantic_hub.retrieval import context, search
from semantic_hub.store import Conflict, Store
from semantic_hub.validation import validate_catalog, visible_catalog
import semantic_hub


def example():
    return Catalog.model_validate(
        yaml.safe_load(Path(semantic_hub.__file__).with_name("demo.yaml").read_text())
    )


class ContractTests(unittest.TestCase):
    def test_example_valid(self):
        self.assertEqual(validate_catalog(example()), [])

    def test_extra_fields_rejected(self):
        data = example().model_dump()
        data["credentials"] = "secret"
        with self.assertRaises(ValidationError):
            Catalog.model_validate(data)

    def test_identifier_injection_rejected(self):
        data = example().model_dump()
        data["models"][0]["table"] = "orders; DROP TABLE x"
        with self.assertRaises(ValidationError):
            Catalog.model_validate(data)

    def test_duplicate_id(self):
        c = example()
        c.metrics.append(c.metrics[0])
        self.assertTrue(validate_catalog(c))

    def test_missing_column(self):
        c = example()
        c.metrics[0].column = "missing"
        self.assertTrue(validate_catalog(c))

    def test_join_requires_complete_key(self):
        c = example()
        c.relationships[0].from_columns = ["shop_id"]
        c.relationships[0].to_columns = ["shop_id"]
        self.assertTrue(validate_catalog(c))

    def test_join_type_mismatch(self):
        c = example()
        c.models[1].columns[1].data_type = "integer"
        self.assertTrue(validate_catalog(c))

    def test_numeric_aggregation(self):
        c = example()
        c.metrics[0].column = "status"
        self.assertTrue(validate_catalog(c))

    def test_visibility_dependency(self):
        c = example()
        c.models[0].visibility = "internal"
        self.assertTrue(validate_catalog(c))

    def test_term_visibility_dependency(self):
        c = example()
        c.terms[0].metric_ids = ["refund_rate"]
        self.assertTrue(validate_catalog(c))

    def test_fixed_filter_type_checked_before_publish(self):
        c = example()
        c.metrics[0].filters[1].value = "false"
        self.assertTrue(validate_catalog(c))

    def test_duplicate_join_columns_rejected(self):
        c = example()
        c.relationships[0].from_columns.append("platform")
        c.relationships[0].to_columns.append("platform")
        self.assertTrue(validate_catalog(c))

    def test_schema_export(self):
        schema = Catalog.model_json_schema()
        self.assertEqual(schema["additionalProperties"], False)

    def test_filter_shapes(self):
        for f in [
            {"field": "order_items.currency", "op": "in", "value": []},
            {"field": "order_items.currency", "value": None},
            {"field": "order_items.currency", "op": "is_null", "value": "x"},
        ]:
            with self.assertRaises(ValidationError):
                Query(metrics=["seller_gmv"], filters=[f])


class CompilerTests(unittest.TestCase):
    def test_currency_guard(self):
        with self.assertRaisesRegex(ValueError, "currency"):
            compile_query(example(), Query(metrics=["seller_gmv"]))

    def test_one_currency_filter(self):
        q = Query(
            metrics=["seller_gmv"], filters=[{"field": "order_items.currency", "value": "USD"}]
        )
        self.assertIn("USD", compile_query(example(), q)["parameters"].values())

    def test_multi_currency_filter_still_needs_group(self):
        q = Query(
            metrics=["seller_gmv"],
            filters=[{"field": "order_items.currency", "op": "in", "value": ["USD", "EUR"]}],
        )
        with self.assertRaises(ValueError):
            compile_query(example(), q)

    def test_composite_join(self):
        result = compile_query(
            example(), Query(metrics=["units_sold"], dimensions=["shops.region"])
        )
        self.assertIn('"order_items"."platform" = "shops"."platform"', result["sql"])
        self.assertIn('"order_items"."shop_id" = "shops"."shop_id"', result["sql"])
        self.assertEqual(result["lineage"]["relationships"], ["order_items_shop"])

    def test_ambiguous_join(self):
        c = example()
        r = c.relationships[0].model_copy(deep=True)
        r.id = "another"
        c.relationships.append(r)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            compile_query(c, Query(metrics=["units_sold"], dimensions=["shops.region"]))

    def test_fanout_join(self):
        c = example()
        c.relationships[0].cardinality = "one_to_many"
        with self.assertRaises(ValueError):
            compile_query(c, Query(metrics=["units_sold"], dimensions=["shops.region"]))

    def test_cross_fact_rejected(self):
        c = example()
        m = c.metrics[1].model_copy(deep=True)
        m.id = "stock"
        m.model = "inventory"
        m.column = "available_qty"
        m.filters = []
        m.time_dimension = "inventory.snapshot_date"
        c.metrics.append(m)
        with self.assertRaisesRegex(ValueError, "Cross-fact"):
            compile_query(c, Query(metrics=["stock", "units_sold"]))

    def test_unknown_metric_and_dimension(self):
        for q in [
            Query(metrics=["unknown"]),
            Query(metrics=["units_sold"], dimensions=["order_items.missing"]),
            Query(metrics=["units_sold"], dimensions=["order_items.quantity"]),
        ]:
            with self.assertRaises(ValueError):
                compile_query(example(), q)

    def test_type_checks(self):
        for value in ["false", 0]:
            q = Query(
                metrics=["units_sold"], filters=[{"field": "order_items.is_sample", "value": value}]
            )
            with self.assertRaises(ValueError):
                compile_query(example(), q)

    def test_bad_date(self):
        q = Query(
            metrics=["units_sold"],
            filters=[{"field": "order_items.order_date", "value": "2026-99-99"}],
        )
        with self.assertRaises(ValueError):
            compile_query(example(), q)

    def test_injection_is_bound(self):
        attack = "USD'; DROP TABLE analytics.order_items; --"
        q = Query(
            metrics=["seller_gmv"], filters=[{"field": "order_items.currency", "value": attack}]
        )
        result = compile_query(example(), q)
        self.assertNotIn(attack, result["sql"])
        self.assertIn(attack, result["parameters"].values())

    def test_dialect_placeholders(self):
        result = compile_query(example(), Query(metrics=["units_sold"], dialect="duckdb"))
        self.assertIn("$p0", result["sql"])
        self.assertNotIn("%(", result["sql"])

    def test_duplicate_selection(self):
        with self.assertRaises(ValueError):
            compile_query(example(), Query(metrics=["units_sold", "units_sold"]))

    def test_actual_aggregate_results(self):
        # SQLite executes the supported common SQL subset with adapted parameter syntax.
        import re

        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.execute("ATTACH DATABASE ':memory:' AS analytics")
        db.execute(
            "CREATE TABLE analytics.order_items(platform,shop_id,order_id,line_id,order_key,sku,order_date,currency,status,is_sample,quantity,seller_net_amount,refund_amount)"
        )
        db.execute("CREATE TABLE analytics.shops(platform,shop_id,shop_name,region,brand)")
        db.executemany(
            "INSERT INTO analytics.shops VALUES(?,?,?,?,?)",
            [("a", "1", "Shop A", "US", "A"), ("b", "1", "Shop B", "SG", "B")],
        )
        rows = [
            ("a", "1", "o1", "1", "a:1:o1", "s1", "2026-11-01", "USD", "paid", False, 2, 20, 2),
            ("a", "1", "o1", "2", "a:1:o1", "s2", "2026-11-01", "USD", "paid", False, 1, 10, 1),
            ("b", "1", "o2", "1", "b:1:o2", "s1", "2026-11-01", "USD", "paid", False, 3, 60, 0),
            (
                "a",
                "1",
                "o3",
                "1",
                "a:1:o3",
                "s1",
                "2026-11-01",
                "USD",
                "cancelled",
                False,
                9,
                90,
                0,
            ),
            ("a", "1", "o4", "1", "a:1:o4", "s1", "2026-11-01", "USD", "paid", True, 8, 80, 0),
        ]
        db.executemany("INSERT INTO analytics.order_items VALUES(" + ",".join("?" * 13) + ")", rows)
        r = compile_query(
            example(),
            Query(
                metrics=["seller_gmv", "units_sold", "order_count"],
                dimensions=["shops.region", "order_items.currency"],
            ),
        )
        sql = re.sub(r"%\((p\d+)\)s", r":\1", r["sql"])
        self.assertEqual(
            db.execute(sql, r["parameters"]).fetchall(),
            [("SG", "USD", 60, 3, 1), ("US", "USD", 30, 3, 1)],
        )
        r = compile_query(
            example(), Query(metrics=["refund_rate"], dimensions=["order_items.currency"])
        )
        sql = re.sub(r"%\((p\d+)\)s", r":\1", r["sql"])
        self.assertAlmostEqual(db.execute(sql, r["parameters"]).fetchone()[1], 3 / 260)
        db.execute("UPDATE analytics.order_items SET seller_net_amount=0")
        self.assertIsNone(db.execute(sql, r["parameters"]).fetchone()[1])


class RetrievalTests(unittest.TestCase):
    def test_chinese_and_english_synonyms(self):
        for q in ["成交额", "seller GMV", "商家折后金额"]:
            self.assertIn("seller_gmv", [r["id"] for r in search(example(), q)])

    def test_context_includes_join_closure(self):
        c = context(example(), "seller_gmv")["context"]
        self.assertIn("shops", [m["id"] for m in c["models"]])
        self.assertEqual(len(c["relationships"]), 1)

    def test_unknown_query(self):
        self.assertFalse(context(example(), "qzxwkj")["matched"])

    def test_budget_fails_without_truncation(self):
        with self.assertRaisesRegex(ValueError, "No partial"):
            context(example(), "GMV", 1000)

    def test_internal_not_in_viewer_retrieval(self):
        c = visible_catalog(example(), "viewer")
        self.assertNotIn("refund_rate", [m.id for m in c.metrics])
        self.assertEqual(search(c, "refund_rate"), [])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name + "/hub.db")
        self.store.seed(example())

    def test_save_publish_restore_pattern(self):
        c = example()
        c.name = "New name"
        rev = self.store.save(c, 1, "alice", "Rename")
        self.assertEqual(self.store.read()["catalog"]["name"], "Commerce Intelligence")
        self.store.publish(rev, "bob")
        self.assertEqual(self.store.read()["catalog"]["name"], "New name")
        old = Catalog.model_validate(self.store.read(revision=1)["catalog"])
        new = self.store.save(old, rev, "alice", "Restore")
        self.assertGreater(new, rev)
        self.assertEqual(self.store.read()["revision"], rev)

    def test_stale_save_and_publish(self):
        self.store.save(example(), 1, "alice", "Update")
        with self.assertRaises(Conflict):
            self.store.save(example(), 1, "bob", "Stale")
        with self.assertRaises(Conflict):
            self.store.publish(1, "bob")

    def test_two_writers_only_one_wins(self):
        def save(_):
            try:
                return self.store.save(example(), 1, "editor", "Concurrent")
            except Conflict:
                return "conflict"

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(save, range(2)))
        self.assertEqual(results.count("conflict"), 1)

    def test_invalid_save_is_atomic(self):
        c = example()
        c.metrics[0].column = "bad"
        with self.assertRaises(ValueError):
            self.store.save(c, 1, "alice", "Broken")
        self.assertEqual(len(self.store.history()["revisions"]), 1)

    def test_seed_idempotent_restart(self):
        store = Store(self.store.path)
        store.seed(example())
        self.assertEqual(len(store.history()["revisions"]), 1)

    def test_digest_deterministic(self):
        rev = self.store.save(example(), 1, "a", "Same")
        self.assertEqual(
            self.store.read(revision=rev)["digest"], self.store.read(revision=1)["digest"]
        )


class ImportTests(unittest.TestCase):
    def test_dbt_import_explicit_grain(self):
        manifest = {
            "nodes": {
                "model.demo.orders": {
                    "resource_type": "model",
                    "name": "orders",
                    "schema": "analytics",
                    "columns": {"id": {"name": "id", "data_type": "int"}},
                    "meta": {"semantic_hub": {"primary_key": ["id"], "owner": "analytics"}},
                }
            }
        }
        c, w = import_dbt(manifest)
        self.assertEqual(validate_catalog(c), [])
        self.assertEqual(c.models[0].primary_key, ["id"])
        self.assertFalse(w)

    def test_dbt_without_key_skipped(self):
        c, w = import_dbt({"nodes": {"x": {"resource_type": "model", "name": "orders"}}})
        self.assertEqual(c.models, [])
        self.assertIn("primary_key", w[0])


if __name__ == "__main__":
    unittest.main()
