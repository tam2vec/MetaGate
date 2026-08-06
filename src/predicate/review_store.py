"""Durable review decisions, human notes, and governed overrides."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ReviewStore:
    """Small SQLite-backed store for the local review service.

    SQLite keeps the hackathon service restart-safe without adding a separate
    database service. The schema is deliberately append-only for decisions,
    notes, and overrides so the audit trail is reproducible.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._recover_oversized_store()
        self._init()

    def _recover_oversized_store(self) -> None:
        """Move a runaway local store aside before it can break the service.

        Review payloads are meant to be small audit records. A historical
        version accidentally nested the full history inside each new payload,
        which can grow a SQLite file until inserts fail. Preserve that file as
        a recovery artifact and start a clean store rather than silently
        deleting evidence or refusing to start.
        """
        try:
            oversized = self.path.exists() and self.path.stat().st_size > 256 * 1024 * 1024
        except OSError:
            oversized = False
        if not oversized:
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        recovery_path = self.path.with_name(f"{self.path.stem}.recovery-{stamp}{self.path.suffix}")
        try:
            self.path.replace(recovery_path)
        except OSError:
            # If the platform cannot rename the file, leave it in place and
            # let SQLite report the underlying problem instead of masking it.
            return

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    urn TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS decisions_lookup
                    ON decisions (urn, capability, id DESC);
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    urn TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    note TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS reviews_lookup
                    ON reviews (urn, capability, id DESC);
                CREATE TABLE IF NOT EXISTS overrides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    urn TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS overrides_lookup
                    ON overrides (urn, capability, id DESC);
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def record_decision(self, payload: dict[str, Any]) -> None:
        stored_payload = dict(payload)
        # History is derived from this table and must never be stored inside a
        # row. Keeping it here causes exponential JSON growth on each check.
        stored_payload.pop("history", None)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO decisions
                (urn, capability, decision, reason, decision_id, evaluated_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    payload.get("entity_urn") or payload.get("urn"),
                    payload.get("capability", ""),
                    payload.get("decision", ""),
                    payload.get("reason", ""),
                    payload.get("decision_id", ""),
                    payload.get("evaluated_at") or self._now(),
                    json.dumps(stored_payload, sort_keys=True),
                ),
            )

    def decisions(self, urn: str, capability: str, limit: int = 25) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT payload_json FROM decisions
                WHERE urn = ? AND capability = ? ORDER BY id DESC LIMIT ?""",
                (urn, capability, limit),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in reversed(rows)]

    def latest_decision(self, urn: str, capability: str) -> dict[str, Any] | None:
        values = self.decisions(urn, capability, limit=1)
        return values[-1] if values else None

    def latest_runs(
        self,
        capability: str | None = None,
        *,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return the latest saved evaluation for each asset/capability pair.

        The ``decisions`` table contains the complete evaluated run payload,
        not just the allow/block headline. Keeping this query here gives the
        review server a durable run list without introducing a second copy of
        the assessment schema.
        """
        query = "SELECT payload_json FROM decisions"
        parameters: tuple[Any, ...] = ()
        if capability:
            query += " WHERE capability = ?"
            parameters = (capability,)
        query += " ORDER BY id DESC LIMIT ?"
        parameters += (max(1, int(limit)) * 20,)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()

        latest: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            payload = json.loads(row["payload_json"])
            urn = payload.get("urn") or payload.get("entity_urn")
            item_capability = payload.get("capability", "")
            if not urn or not item_capability:
                continue
            latest.setdefault((urn, item_capability), payload)
            if len(latest) >= limit:
                break
        return list(reversed(list(latest.values())))

    def add_review(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO reviews
                (urn, capability, verdict, note, actor, saved_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    record["urn"], record["capability"], record["verdict"],
                    record["note"], record.get("actor", "local-user"), record["saved_at"],
                ),
            )
        return record

    def reviews(self, urn: str, capability: str, limit: int = 25) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT urn, capability, verdict, note, actor, saved_at
                FROM reviews WHERE urn = ? AND capability = ?
                ORDER BY id DESC LIMIT ?""",
                (urn, capability, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def add_override(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO overrides
                (urn, capability, decision, reason, actor, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    record["urn"], record["capability"], record["decision"],
                    record["reason"], record["actor"], record["role"], record["created_at"],
                ),
            )
        return record

    def latest_override(self, urn: str, capability: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT urn, capability, decision, reason, actor, role, created_at
                FROM overrides WHERE urn = ? AND capability = ? ORDER BY id DESC LIMIT 1""",
                (urn, capability),
            ).fetchone()
        return dict(row) if row else None
