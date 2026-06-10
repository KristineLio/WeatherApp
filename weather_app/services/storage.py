from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import datetime as dt

_RECENT_DUPLICATE_SECONDS = 60
_MAX_HISTORY_ROWS = 200

def default_db_path() -> Path:
    """
    Same philosophy as SettingsStore: store in user home for portability.
      ~/.weather_app/weather.db
    """
    home = Path.home()
    return home / ".weather_app" / "weather.db"


@dataclass(frozen=True)
class FavoriteRow:
    city: str
    lat: float | None
    lon: float | None
    country: str | None
    added_at: str


@dataclass(frozen=True)
class HistoryRow:
    id: int
    city: str
    lat: float | None
    lon: float | None
    searched_at: str


class StorageRepo:
    """
    Small SQLite repo:
      - favorites(city PRIMARY KEY, lat, lon, country, added_at)
      - search_history(id PK, city, lat, lon, searched_at)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # -------------------------
    # DB init
    # -------------------------
    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row

        try:
            con.execute("PRAGMA journal_mode=WAL;")
        except sqlite3.OperationalError:
            # Fallback for environments where WAL files can't be created/locked
            con.execute("PRAGMA journal_mode=DELETE;")

        con.execute("PRAGMA foreign_keys=ON;")
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS favorites (
                    city TEXT PRIMARY KEY,
                    lat REAL,
                    lon REAL,
                    country TEXT,
                    added_at TEXT NOT NULL
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city TEXT NOT NULL,
                    lat REAL,
                    lon REAL,
                    searched_at TEXT NOT NULL
                )
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_history_id ON search_history(id DESC)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_history_city ON search_history(city)")

    # -------------------------
    # Helpers
    # -------------------------
    def _now_iso(self) -> str:
        return dt.datetime.now().replace(microsecond=0).isoformat()

    # -------------------------
    # Favorites
    # -------------------------
    def is_favorite(self, city: str) -> bool:
        city = (city or "").strip()
        if not city:
            return False
        with self._connect() as con:
            row = con.execute(
                "SELECT 1 FROM favorites WHERE city = ? LIMIT 1",
                (city,),
            ).fetchone()
            return row is not None

    def add_favorite(self, *, city: str, lat: float | None, lon: float | None, country: str | None) -> None:
        city = (city or "").strip()
        if not city:
            return
        with self._connect() as con:
            # INSERT OR REPLACE keeps it simple if you favorite the same city again
            con.execute(
                """
                INSERT OR REPLACE INTO favorites(city, lat, lon, country, added_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (city, lat, lon, country, self._now_iso()),
            )

    def remove_favorite(self, city: str) -> None:
        city = (city or "").strip()
        if not city:
            return
        with self._connect() as con:
            con.execute("DELETE FROM favorites WHERE city = ?", (city,))

    def list_favorites(self) -> list[FavoriteRow]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT city, lat, lon, country, added_at
                FROM favorites
                ORDER BY added_at DESC
                """
            ).fetchall()
        return [
            FavoriteRow(
                city=r["city"],
                lat=r["lat"],
                lon=r["lon"],
                country=r["country"],
                added_at=r["added_at"],
            )
            for r in rows
        ]

    # -------------------------
    # Search history
    # -------------------------
    def add_history(self, *, city: str, lat: float | None, lon: float | None) -> None:
        city = (city or "").strip()
        if not city:
            return

        now = self._now_iso()

        with self._connect() as con:
            latest = con.execute(
                """
                SELECT id, city, searched_at
                FROM search_history
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

            should_replace_latest = False

            if latest is not None:
                latest_city = (latest["city"] or "").strip().lower()
                current_city = city.lower()

                if latest_city == current_city:
                    try:
                        latest_time = dt.datetime.fromisoformat(latest["searched_at"])
                        now_time = dt.datetime.fromisoformat(now)
                        age_seconds = (now_time - latest_time).total_seconds()

                        should_replace_latest = age_seconds <= _RECENT_DUPLICATE_SECONDS
                    except ValueError:
                        should_replace_latest = False

            if should_replace_latest:
                con.execute(
                    """
                    UPDATE search_history
                    SET city = ?, lat = ?, lon = ?, searched_at = ?
                    WHERE id = ?
                    """,
                    (city, lat, lon, now, int(latest["id"])),
                )
            else:
                con.execute(
                    """
                    INSERT INTO search_history(city, lat, lon, searched_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (city, lat, lon, now),
                )

            con.execute(
                """
                DELETE FROM search_history
                WHERE id NOT IN (
                    SELECT id
                    FROM search_history
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (_MAX_HISTORY_ROWS,),
            )

    def list_history(self, *, limit: int = 20) -> list[HistoryRow]:
        lim = max(1, int(limit))
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT id, city, lat, lon, searched_at
                FROM search_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (lim,),
            ).fetchall()
        return [
            HistoryRow(
                id=int(r["id"]),
                city=r["city"],
                lat=r["lat"],
                lon=r["lon"],
                searched_at=r["searched_at"],
            )
            for r in rows
        ]

    def clear_history(self) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM search_history")
    
    def remove_history(self, history_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM search_history WHERE id = ?", (int(history_id),))
    
    def clear_favorites(self) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM favorites")