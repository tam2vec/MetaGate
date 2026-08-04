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
        self._init()

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
                    json.dumps(payload, sort_keys=True),
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

