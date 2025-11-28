"""Seed script to populate the SmartBowl SQLite DB with mock sensor and hydration data.

Run from project root:
    python scripts/seed_db.py --days 30 --events-per-day 3
"""
from __future__ import annotations
import argparse
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on sys.path so `from app.core import db` works when
# executing this script directly (python scripts/seed_db.py).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import db
from app.core.config import SUB_TOPIC


def _build_payload(vi: float, vf: float, dur: float) -> dict:
    return {
        "volumen_inicio": round(vi, 2),
        "volumen_fin": round(vf, 2),
        "duracion": round(dur, 2),
    }


def seed_hydration(days: int = 30, min_events: int = 2, max_events: int = 4) -> int:
    """Populate hydration_events, hydration_log and readings for the last N days."""
    base_date = datetime.utcnow().date()
    total_events = 0

    for offset in range(days):
        target_day = base_date - timedelta(days=offset)
        # choose how many drinking sessions for that day
        sessions = random.randint(min_events, max_events)
        # choose timestamps (sorted) within the day between 5:00 and 23:00
        hours = sorted(random.sample(range(5, 23), sessions))
        last_ts: int | None = None

        for idx, hour in enumerate(hours):
            minute = random.randint(0, 59)
            ts = int(datetime(target_day.year, target_day.month, target_day.day, hour, minute).timestamp())
            gap_minutes = ((ts - last_ts) / 60.0) if last_ts else 0.0
            last_ts = ts

            # generate volumes/durations
            start_volume = random.uniform(600, 1100)
            consumed = random.uniform(20, 160)
            end_volume = max(0.0, start_volume - consumed)
            duration = random.uniform(10, 180)

            payload_obj = _build_payload(start_volume, end_volume, duration)

            ml_consumed = max(0.0, start_volume - end_volume)
            extra_info = {
                "payload": payload_obj,
                "ml_consumed": round(ml_consumed, 2),
                "ml_consumidos": round(ml_consumed, 2),
                "gap_min": round(max(gap_minutes, 0.0), 2),
            }

            # persist hydration event + aggregated daily ml
            db.save_hydration_event(start_volume, end_volume, duration, ts, extra=json.dumps(extra_info))
            ml = max(0, int(round(ml_consumed)))
            db.upsert_daily_ml(target_day.strftime("%Y-%m-%d"), ml)

            # mimic MQTT inbound message into readings table (single topic)
            db.save_reading(SUB_TOPIC, json.dumps(payload_obj), ts)

            total_events += 1

    return total_events


def print_summary(limit: int = 14) -> None:
    conn = db.get_conn()
    c = conn.cursor()
    c.execute("SELECT day, ml, updated_ts FROM hydration_log ORDER BY day DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    print("Últimos registros en hydration_log:")
    for r in rows:
        ts = datetime.utcfromtimestamp(r["updated_ts"]).isoformat() if r["updated_ts"] else "-"
        print(f"  {r['day']}: {r['ml']} ml (actualizado {ts})")

    c.execute("SELECT topic, COUNT(*) AS cnt FROM readings GROUP BY topic")
    print("\nMensajes en readings por topic:")
    for row in c.fetchall():
        print(f"  {row['topic']}: {row['cnt']}")


def main(args: argparse.Namespace) -> None:
    print(f"Generando datos de hidratación para {args.days} días...")
    events = seed_hydration(args.days, args.min_events, args.max_events)
    print(f"Insertados {events} eventos de hidratación")

    print_summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="Días de historial a generar")
    parser.add_argument("--min-events", type=int, default=2, help="Eventos mínimos por día")
    parser.add_argument("--max-events", type=int, default=4, help="Eventos máximos por día")
    args = parser.parse_args()
    main(args)
