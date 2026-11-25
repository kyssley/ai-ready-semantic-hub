import tempfile
import unittest
from fastapi.testclient import TestClient
from semantic_hub.api import create_app
from test_core import example

TOKENS = {
    c * 40: {"name": name, "role": role}
    for c, name, role in [
        ("a", "alice", "admin"),
        ("e", "emma", "editor"),
        ("v", "victor", "viewer"),
    ]
}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = create_app(db_path=self.tmp.name + "/api.db", demo=False, tokens=TOKENS)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.app.state.store.save(example(), 1, "setup", "Load synthetic catalog")
        self.app.state.store.publish(2, "setup")

    def headers(self, role="a"):
        return {"Authorization": "Bearer " + role * 40}

    def test_fail_closed_configuration(self):
        with self.assertRaises(ValueError):
            create_app(db_path=self.tmp.name + "/other.db", demo=False, tokens={})

    def test_health_public_catalog_private(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/api/catalog").status_code, 401)

    def test_viewer_filtered_on_every_read(self):
        h = self.headers("v")
        for url in [
            "/api/catalog",
            "/api/export?format=json",
            "/api/export",
            "/api/search?q=refund_rate",
            "/api/graph",
        ]:
            r = self.client.get(url, headers=h)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("refund_rate", r.text)
        r = self.client.post("/api/context", headers=h, json={"question": "refund_rate"})
        self.assertFalse(r.json()["matched"])
        r = self.client.post(
            "/api/compile",
            headers=h,
            json={"metrics": ["refund_rate"], "dimensions": ["order_items.currency"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_viewer_cannot_read_drafts_or_history(self):
        for url in [
            "/api/catalog?channel=draft",
            "/api/export?channel=draft",
            "/api/history",
            "/api/revisions/1",
        ]:
            self.assertEqual(self.client.get(url, headers=self.headers("v")).status_code, 403)

    def test_viewer_cannot_mutate(self):
        body = {"catalog": example().model_dump(), "expected_revision": 2, "message": "x"}
        self.assertEqual(
            self.client.put("/api/draft", headers=self.headers("v"), json=body).status_code, 403
        )

    def test_editor_can_save_not_publish(self):
        c = example().model_dump()
        c["name"] = "New name"
        r = self.client.put(
            "/api/draft",
            headers=self.headers("e"),
            json={"catalog": c, "expected_revision": 2, "message": "Rename"},
        )
        self.assertEqual(r.status_code, 200)
        rev = r.json()["revision"]
        self.assertEqual(
            self.client.post(
                "/api/publish", headers=self.headers("e"), json={"expected_revision": rev}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/api/catalog", headers=self.headers()).json()["catalog"]["name"],
            "Commerce Intelligence",
        )
        self.assertEqual(
            self.client.post(
                "/api/publish", headers=self.headers(), json={"expected_revision": rev}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/api/catalog", headers=self.headers()).json()["catalog"]["name"],
            "New name",
        )

    def test_conflict_is_409(self):
        r = self.client.put(
            "/api/draft",
            headers=self.headers(),
            json={"catalog": example().model_dump(), "expected_revision": 1, "message": "Stale"},
        )
        self.assertEqual(r.status_code, 409)

    def test_restore_new_draft(self):
        r = self.client.post(
            "/api/restore", headers=self.headers(), json={"revision": 1, "expected_revision": 2}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["revision"], 3)
        self.assertEqual(
            self.client.get("/api/catalog", headers=self.headers()).json()["revision"], 2
        )

    def test_unknown_revision_404(self):
        self.assertEqual(
            self.client.get("/api/revisions/999", headers=self.headers()).status_code, 404
        )

    def test_bad_yaml_and_semantics(self):
        for text in ["x: [", "!!python/object/apply:os.system [echo unsafe]", "schema_version: 2"]:
            r = self.client.post("/api/parse-yaml", headers=self.headers(), json={"yaml": text})
            self.assertEqual(r.status_code, 422)
        data = example().model_dump()
        data["metrics"][0]["column"] = "bad"
        r = self.client.post("/api/validate", headers=self.headers(), json=data)
        self.assertFalse(r.json()["valid"])

    def test_invalid_query_limit(self):
        r = self.client.post(
            "/api/compile", headers=self.headers(), json={"metrics": ["units_sold"], "limit": 10001}
        )
        self.assertEqual(r.status_code, 422)

    def test_large_body_rejected(self):
        r = self.client.post("/api/parse-yaml", headers=self.headers(), content=b"x" * 1_000_001)
        self.assertEqual(r.status_code, 413)

    def test_response_security_headers(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("script-src 'self'", r.headers["Content-Security-Policy"])
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")

    def test_internal_visible_to_editor(self):
        r = self.client.get("/api/catalog", headers=self.headers("e"))
        self.assertIn("refund_rate", r.text)

    def test_openapi_contract(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/api/compile", schema["paths"])
        self.assertIn("HTTPBearer", schema["components"]["securitySchemes"])


if __name__ == "__main__":
    unittest.main()
