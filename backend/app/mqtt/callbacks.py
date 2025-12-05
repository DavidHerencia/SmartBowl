from __future__ import annotations
import json
import time
from typing import Any, Dict, Optional
from datetime import datetime
from ..core import db
from ..core.config import SUB_TOPIC, LEVEL_TOPIC


# In-memory cache for the most recent hydration message and derived status.
latest_readings: Dict[str, Any] = {
    "topics": {},
    "raw_last": None,
    "hydration_last": None,
    "level_last": None,
    "last_event": None,
    "status": {},
    "last_command": None,
}

_estimated_capacity_ml: float = 0.0
_previous_event_ts: Optional[int] = None


def on_connect(client, userdata, flags, rc):
    print("MQTT connected, rc=", rc)
    if SUB_TOPIC:
        client.subscribe(SUB_TOPIC)
        print("Subscribed to", SUB_TOPIC)
    if LEVEL_TOPIC and LEVEL_TOPIC != SUB_TOPIC:
        client.subscribe(LEVEL_TOPIC)
        print("Subscribed to", LEVEL_TOPIC)
def _store_raw(topic: str, payload: str, ts: int, parsed: Optional[Dict[str, Any]]) -> None:
    entry: Dict[str, Any] = {"topic": topic, "raw": payload, "ts": ts}
    if parsed is not None:
        entry["parsed"] = parsed

    latest_readings["raw_last"] = entry
    latest_readings.setdefault("topics", {})[topic] = entry

    try:
        db.save_reading(topic, payload, ts)
    except Exception as e:
        print("DB save error:", e)


def _handle_level_update(topic: str, payload: str, ts: int, data: Dict[str, Any]) -> None:
    global _estimated_capacity_ml

    try:
        volumen = float(data["volumen"])
    except Exception as exc:
        print("Invalid level payload values", exc)
        _store_raw(topic, payload, ts, data)
        return

    status = latest_readings.setdefault("status", {})
    status["current_volume_ml"] = volumen
    status["last_seen_ts"] = ts

    if volumen > _estimated_capacity_ml:
        _estimated_capacity_ml = volumen

    capacity = status.get("estimated_capacity_ml") or _estimated_capacity_ml
    if not capacity and volumen > 0:
        capacity = volumen
        status["estimated_capacity_ml"] = capacity

    if capacity:
        tank_percent = max(0.0, min(100.0, (volumen / capacity) * 100.0))
        status["tank_level_percent"] = tank_percent

    latest_readings["level_last"] = {
        "ts": ts,
        "topic": topic,
        "volumen": volumen,
    }

    _store_raw(topic, payload, ts, data)


def _handle_hydration_event(topic: str, payload: str, ts: int) -> None:
    global _estimated_capacity_ml, _previous_event_ts

    try:
        data = json.loads(payload)
    except Exception:
        print("Invalid hydration payload: not JSON")
        _store_raw(topic, payload, ts, None)
        return

    if not isinstance(data, dict):
        print("Invalid hydration payload: not an object")
        _store_raw(topic, payload, ts, None)
        return

    required_keys = (
        "volumen_inicio",
        "volumen_fin",
        "duracion",
    )
    if not all(k in data for k in required_keys):
        print("Invalid hydration payload: missing required keys")
        _store_raw(topic, payload, ts, data)
        return

    try:
        vi = float(data["volumen_inicio"])
        vf = float(data["volumen_fin"])
        dur = float(data["duracion"])
    except Exception as exc:
        print("Invalid hydration payload values", exc)
        _store_raw(topic, payload, ts, data)
        return

    ml_consumed = max(0.0, vi - vf)

    gap_min: Optional[float] = None
    if _previous_event_ts is not None:
        gap_min = max(0.0, (ts - _previous_event_ts) / 60.0)
    _previous_event_ts = ts

    if vi > _estimated_capacity_ml:
        _estimated_capacity_ml = vi

    tank_percent: Optional[float] = None
    if _estimated_capacity_ml > 0:
        tank_percent = max(0.0, min(100.0, (vf / _estimated_capacity_ml) * 100.0))

    event_info = {
        "ts": ts,
        "volumen_inicio": vi,
        "volumen_fin": vf,
        "duracion": dur,
        "ml_consumed": ml_consumed,
        "ml_consumidos": ml_consumed,
        "gap_min": gap_min,
        "tank_percent": tank_percent,
    }

    latest_readings["hydration_last"] = event_info.copy()
    latest_readings["last_event"] = event_info

    status = latest_readings.setdefault("status", {})
    status["last_seen_ts"] = ts
    status["estimated_capacity_ml"] = _estimated_capacity_ml if _estimated_capacity_ml else None
    status["tank_level_percent"] = tank_percent
    status["last_drink_ts"] = ts
    status["last_drink_ml"] = ml_consumed
    status["current_volume_ml"] = vf

    _store_raw(topic, payload, ts, data)

    extra = {
        "payload": data,
        "ml_consumed": ml_consumed,
        "ml_consumidos": ml_consumed,
        "gap_min": gap_min,
        "tank_percent": tank_percent,
    }

    try:
        db.save_hydration_event(vi, vf, dur, ts, extra=json.dumps(extra))
        day = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        db.upsert_daily_ml(day, int(round(ml_consumed)))
    except Exception as e:
        print("Error saving hydration event:", e)


def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = msg.payload.decode("utf-8", errors="ignore")
    except Exception:
        payload = str(msg.payload)

    ts = int(time.time())
    # Because we now use a single inbound topic, attempt to parse as JSON and
    # always handle hydration fields if present; otherwise just store raw reading.
    try:
        obj = json.loads(payload)
    except Exception:
        obj = None

    if isinstance(obj, dict) and all(k in obj for k in ("volumen_inicio", "volumen_fin", "duracion")):
        _handle_hydration_event(topic, payload, ts)
    elif isinstance(obj, dict) and "volumen" in obj:
        _handle_level_update(topic, payload, ts, obj)
    else:
        _store_raw(topic, payload, ts, obj if isinstance(obj, dict) else None)

    print(f"MQTT msg: {topic} -> {payload}")
