from __future__ import annotations
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, cast
from pathlib import Path
from .config import DB_PATH

_conn_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        with _conn_lock:
            if _conn is None:
                Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
                _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                _conn.row_factory = sqlite3.Row
                _init_db(_conn)
    return _conn


def _init_db(conn: sqlite3.Connection) -> None:
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            payload TEXT NOT NULL,
            ts INTEGER NOT NULL
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS hydration_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            volumen_inicio REAL,
            volumen_fin REAL,
            duracion REAL,
            extra TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS hydration_log (
            day TEXT PRIMARY KEY,
            ml INTEGER NOT NULL,
            updated_ts INTEGER NOT NULL
        )
        """
    )
    conn.commit()


def save_reading(topic: str, payload: str, ts: Optional[int] = None) -> int:
    if ts is None:
        ts = int(time.time())
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO readings (topic, payload, ts) VALUES (?, ?, ?)", (topic, payload, ts))
    conn.commit()
    return cast(int, c.lastrowid)


def save_hydration_event(volumen_inicio: float, volumen_fin: float, duracion: float, ts: Optional[int] = None, extra: Optional[str] = None) -> int:
    if ts is None:
        ts = int(time.time())
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO hydration_events (ts, volumen_inicio, volumen_fin, duracion, extra) VALUES (?, ?, ?, ?, ?)",
        (ts, volumen_inicio, volumen_fin, duracion, extra),
    )
    conn.commit()
    return cast(int, c.lastrowid)


def upsert_daily_ml(day: str, ml: int) -> None:
    ts = int(time.time())
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT ml FROM hydration_log WHERE day = ?", (day,))
    row = c.fetchone()
    if row:
        new_ml = int(row["ml"]) + ml
        c.execute("UPDATE hydration_log SET ml = ?, updated_ts = ? WHERE day = ?", (new_ml, ts, day))
    else:
        c.execute("INSERT INTO hydration_log (day, ml, updated_ts) VALUES (?, ?, ?)", (day, ml, ts))
    conn.commit()


def get_recent_readings(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT topic, payload, ts FROM readings ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    return [dict(r) for r in rows]


def get_last_reading_for_topic(topic: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT topic, payload, ts FROM readings WHERE topic = ? ORDER BY id DESC LIMIT 1", (topic,))
    row = c.fetchone()
    return dict(row) if row else None


def get_hydration_for_day(day: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT day, ml, updated_ts FROM hydration_log WHERE day = ?", (day,))
    r = c.fetchone()
    return dict(r) if r else None


def get_hydration_days(limit: int = 7) -> List[Dict[str, Any]]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT day, ml, updated_ts FROM hydration_log ORDER BY day DESC LIMIT ?", (limit,))
    return [dict(r) for r in c.fetchall()]
