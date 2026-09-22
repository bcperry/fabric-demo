import os
from uuid import UUID

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class Store:
    def __init__(self, credential):
        self.credential = credential

    @staticmethod
    def normalize(row):
        if row is None:
            return None
        return {name: str(UUID(str(value))) if name in {"run_id", "actor", "idempotency_key"} else value
                for name, value in row.items()}

    def connect(self):
        token = self.credential.get_token("https://ossrdbms-aad.database.windows.net/.default").token
        return psycopg.connect(host="pg-mda-demo-4u6mawdzlpyh4.postgres.database.azure.com",
                               dbname="mdaoperations", user=os.environ["PGUSER"], password=token,
                               sslmode="require", connect_timeout=10, row_factory=dict_row)

    def reserve(self, manifest, digest):
        with self.connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(724103)")
            existing = connection.execute("SELECT * FROM live_test_control.runs WHERE actor=%s AND idempotency_key=%s",
                                          (manifest["actor"], manifest["input"]["idempotency_key"])).fetchone()
            if existing:
                if existing["manifest"]["input"] != manifest["input"]:
                    raise HTTPException(409, "Idempotency key already used")
                return self.normalize(existing), False
            if connection.execute("SELECT 1 FROM live_test_control.runs WHERE state IN ('REQUESTED','STARTING','RUNNING','START_UNKNOWN')").fetchone():
                raise HTTPException(409, "Launch unavailable")
            row = connection.execute("""
                INSERT INTO live_test_control.runs (run_id,actor,idempotency_key,manifest,manifest_sha256,image,state)
                VALUES (%s,%s,%s,%s,%s,%s,'REQUESTED') RETURNING *
                """, (manifest["run_id"], manifest["actor"], manifest["input"]["idempotency_key"],
                      Jsonb(manifest), digest, manifest["image"])).fetchone()
            return self.normalize(row), True

    def get(self, run_id):
        with self.connect() as connection:
            return self.normalize(connection.execute(
                "SELECT * FROM live_test_control.runs WHERE run_id=%s", (run_id,)).fetchone())

    def list(self, actor):
        with self.connect() as connection:
            if actor is None:
                rows = connection.execute(
                    "SELECT * FROM live_test_control.runs ORDER BY created_at DESC LIMIT 100").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM live_test_control.runs WHERE actor=%s ORDER BY created_at DESC LIMIT 100",
                    (actor,)).fetchall()
            return [self.normalize(row) for row in rows]

    def transition(self, run_id, previous, state, execution=None):
        with self.connect() as connection:
            row = connection.execute("""
                UPDATE live_test_control.runs SET state=%s, execution_id=COALESCE(execution_id,%s)
                WHERE run_id=%s AND state=%s RETURNING *
                """, (state, execution, run_id, previous)).fetchone()
            if row is None:
                raise HTTPException(409, "Run state changed")
            return self.normalize(row)