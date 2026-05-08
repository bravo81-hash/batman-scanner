"""SQLite storage for scan history."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from scanner.models import BatmanCandidate, ScanSettings


def init_db(db_path: str = "data/scan_history.db") -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                settings_json TEXT NOT NULL,
                candidate_json TEXT NOT NULL,
                score REAL NOT NULL,
                rank INTEGER NOT NULL
            )
            """
        )


def save_scan_history(
    settings: ScanSettings,
    candidates: list[BatmanCandidate],
    db_path: str = "data/scan_history.db",
    limit: int = 20,
) -> str:
    """Persist the top candidates from one scan and return the scan id."""
    init_db(db_path)
    timestamp = datetime.now().isoformat(timespec="seconds")
    scan_id = f"{settings.symbol}-{timestamp}"
    settings_json = json.dumps(settings.to_dict(), sort_keys=True)

    rows = [
        (
            scan_id,
            timestamp,
            settings.symbol,
            settings_json,
            json.dumps(candidate.to_dict(), sort_keys=True),
            candidate.score,
            candidate.rank,
        )
        for candidate in candidates[:limit]
    ]

    with sqlite3.connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO scan_history
            (scan_id, timestamp, symbol, settings_json, candidate_json, score, rank)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return scan_id

