"""SQLite snapshots. BEGIN IMMEDIATE + expected revision prevent lost updates."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .models import Catalog
from .validation import require_valid


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS snapshots (
                revision INTEGER PRIMARY KEY AUTOINCREMENT,
                document TEXT NOT NULL, digest TEXT NOT NULL,
                actor TEXT NOT NULL, message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );
            CREATE TABLE IF NOT EXISTS state (
                id INTEGER PRIMARY KEY CHECK(id=1),
                draft INTEGER NOT NULL, published INTEGER
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
                revision INTEGER NOT NULL, actor TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );
            PRAGMA user_version=1;
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _insert(self, db, catalog, actor, message):
        document = json.dumps(
            catalog.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        digest = hashlib.sha256(document.encode()).hexdigest()
        return db.execute(
            "INSERT INTO snapshots(document,digest,actor,message) VALUES(?,?,?,?)",
            (document, digest, actor, message),
        ).lastrowid

    def seed(self, catalog: Catalog, actor="system"):
        require_valid(catalog)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT id FROM state").fetchone():
                return
            rev = self._insert(db, catalog, actor, "Initialize catalog")
            db.execute("INSERT INTO state VALUES(1,?,?)", (rev, rev))
            db.execute(
                "INSERT INTO audit(action,revision,actor) VALUES('initialize',?,?)", (rev, actor)
            )

    def read(self, channel="published", revision=None):
        with self.connect() as db:
            state = db.execute("SELECT * FROM state WHERE id=1").fetchone()
            rev = revision if revision is not None else state[channel]
            row = db.execute("SELECT * FROM snapshots WHERE revision=?", (rev,)).fetchone()
            if row is None:
                raise KeyError("Revision not found")
            return {
                "revision": row["revision"],
                "digest": row["digest"],
                "created_at": row["created_at"],
                "catalog": json.loads(row["document"]),
            }

    def save(self, catalog: Catalog, expected: int, actor: str, message: str):
        require_valid(catalog)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT draft FROM state WHERE id=1").fetchone()[0]
            if current != expected:
                raise Conflict(
                    f"Draft changed: expected {expected}, current {current}; reload before saving"
                )
            rev = self._insert(db, catalog, actor, message)
            db.execute("UPDATE state SET draft=? WHERE id=1", (rev,))
            db.execute("INSERT INTO audit(action,revision,actor) VALUES('save',?,?)", (rev, actor))
            return rev

    def publish(self, expected: int, actor: str):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT draft FROM state WHERE id=1").fetchone()[0]
            if current != expected:
                raise Conflict("Draft changed; reload and review before publishing")
            document = db.execute(
                "SELECT document FROM snapshots WHERE revision=?", (current,)
            ).fetchone()[0]
            require_valid(Catalog.model_validate_json(document))
            db.execute("UPDATE state SET published=? WHERE id=1", (current,))
            db.execute(
                "INSERT INTO audit(action,revision,actor) VALUES('publish',?,?)", (current, actor)
            )
            return current

    def history(self):
        with self.connect() as db:
            return {
                "state": dict(
                    db.execute("SELECT draft,published FROM state WHERE id=1").fetchone()
                ),
                "revisions": [
                    dict(r)
                    for r in db.execute(
                        "SELECT revision,digest,actor,message,created_at FROM snapshots ORDER BY revision DESC LIMIT 100"
                    )
                ],
                "audit": [
                    dict(r) for r in db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 100")
                ],
            }
