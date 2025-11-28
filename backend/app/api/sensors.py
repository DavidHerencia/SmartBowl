from __future__ import annotations
import copy
import json
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any
from ..mqtt import callbacks
from ..core import db
from ..core.config import SUB_TOPIC

router = APIRouter(prefix="/sensors", tags=["sensors"])


@router.get("/latest")
def latest_readings() -> Dict[str, Any]:
    state = callbacks.latest_readings
    topics = [copy.deepcopy(v) for v in (state.get("topics") or {}).values()]

    return {
        "subscribed_topic": SUB_TOPIC,
        "raw_last": copy.deepcopy(state.get("raw_last")),
        "hydration_last": copy.deepcopy(state.get("hydration_last")),
        "topics": topics,
        "last_event": copy.deepcopy(state.get("last_event")),
        "status": copy.deepcopy(state.get("status")),
        "last_command": copy.deepcopy(state.get("last_command")),
    }


@router.get("/raw")
def raw_readings(limit: int = Query(50, ge=1, le=1000)):
    rows = db.get_recent_readings(limit)
    formatted = []
    for row in rows:
        parsed = None
        try:
            parsed = json.loads(row["payload"])
        except Exception:
            parsed = None
        formatted.append({
            "topic": row["topic"],
            "raw": row["payload"],
            "parsed": parsed,
            "ts": row["ts"],
        })
    return {"count": len(formatted), "rows": formatted}


@router.get("/topic")
def get_topic(topic: str):
    state = callbacks.latest_readings
    cache = (state.get("topics") or {})
    entry = cache.get(topic)
    if entry:
        return {
            "topic": topic,
            "raw": entry.get("raw"),
            "parsed": entry.get("parsed"),
            "ts": entry.get("ts"),
            "source": "cache",
        }

    row = db.get_last_reading_for_topic(topic)
    if row:
        parsed = None
        try:
            parsed = json.loads(row["payload"])
        except Exception:
            parsed = None
        return {
            "topic": topic,
            "raw": row["payload"],
            "parsed": parsed,
            "ts": row["ts"],
            "source": "db",
        }

    raise HTTPException(status_code=404, detail="Topic not found")
