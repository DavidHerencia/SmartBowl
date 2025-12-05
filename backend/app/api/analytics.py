from __future__ import annotations
import time
from collections import Counter
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional, Tuple
from ..core import db
from ..core.config import SUB_TOPIC
from ..mqtt import callbacks
from datetime import datetime

router = APIRouter(prefix="/analytics", tags=["analytics"])


_DAY_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
_LEVEL_BY_LABEL = {"Adecuado": "high", "Medio": "medium", "Mínimo": "low"}


def _short_day_label(day_str: str) -> str:
    try:
        dt = datetime.strptime(day_str, "%Y-%m-%d")
        return _DAY_LABELS[dt.weekday()]
    except Exception:
        return day_str
def _ts_to_iso(ts: Optional[int]) -> Optional[str]:
    if not ts:
        return None
    try:
        return datetime.utcfromtimestamp(int(ts)).isoformat() + "Z"
    except Exception:
        return None


# Hydration aggregation endpoints (simple, inline logic)
@router.get("/hydration/today")
def hydration_today() -> Dict[str, Any]:
    day = datetime.utcnow().strftime("%Y-%m-%d")
    rec = db.get_hydration_for_day(day)
    return rec or {"day": day, "ml": 0, "updated_ts": None}


@router.get("/hydration/week")
def hydration_week(days: int = Query(7, ge=1, le=30)) -> List[Dict[str, Any]]:
    out = []
    today = datetime.utcnow().date()
    for i in range(days):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        rec = db.get_hydration_for_day(d) or {"day": d, "ml": 0, "updated_ts": None}
        out.append(rec)
    return out


def _hydration_week_with_labels(days: int = 7) -> Dict[str, Any]:
    today = datetime.utcnow().date()
    rows: List[Dict[str, Any]] = []
    for i in range(days):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        rec = db.get_hydration_for_day(d) or {"day": d, "ml": 0, "updated_ts": None}
        rows.append(rec)

    rows.sort(key=lambda r: r["day"])  # ascending by date

    events = []
    for r in rows:
        events.append({"day": r["day"], "ml": r["ml"], "duracion": 0.0, "hour": 12.0, "gap": 0.0})

    km_summary = _run_kmeans(events, n_clusters=3) if events else {"assignments": [], "centers": []}
    assignments_lookup = {a["day"]: a for a in km_summary.get("assignments", []) or []}

    items = []
    for rec in rows:
        assign = assignments_lookup.get(rec["day"])
        human_label = assign.get("label") if assign else None
        level_key = str(human_label) if human_label is not None else None
        level = _LEVEL_BY_LABEL.get(level_key, "medium") if level_key else "medium"
        items.append({
            "day": _short_day_label(rec["day"]),
            "date": rec["day"],
            "value_ml": rec.get("ml", 0),
            "level": level,
            "human_label": human_label,
            "cluster": assign.get("cluster") if assign else None,
        })

    return {"items": items, "kmeans": km_summary}


# --- KMeans clustering and classification (moved here for simplicity) ---
import numpy as np
from sklearn.cluster import KMeans
from datetime import timedelta


def _prepare_features(events: List[Dict[str, Any]]) -> Tuple[np.ndarray, List[str]]:
    X = []
    keys: List[str] = []
    for e in events:
        ml = float(e.get("ml", 0))
        dur = float(e.get("duracion", 0))
        hour = float(e.get("hour", 12))
        gap = float(e.get("gap", 0))
        X.append([ml, dur, hour, gap])
        keys.append(e.get("day", ""))
    return np.array(X), keys


def _run_kmeans(events: List[Dict[str, Any]], n_clusters: int = 3, random_state: int = 42) -> Dict[str, Any]:
    X, keys = _prepare_features(events)
    if X.shape[0] == 0:
        return {"error": "no data"}
    km = KMeans(n_clusters=min(n_clusters, max(1, X.shape[0])), random_state=random_state)
    km.fit(X)
    labels = km.labels_
    centers = km.cluster_centers_
    # Map clusters by ml descending to human labels
    order = sorted(range(len(centers)), key=lambda i: centers[i][0], reverse=True)
    human = ["Adecuado", "Medio", "Mínimo"]
    label_map: Dict[int, str] = {}
    for idx, cluster_idx in enumerate(order):
        label_map[cluster_idx] = human[idx] if idx < len(human) else f"Cluster {idx}"

    assignments = []
    for k, lbl in zip(keys, labels):
        assignments.append({"day": k, "cluster": int(lbl), "label": label_map.get(int(lbl), "unknown")})

    return {"centers": centers.tolist(), "assignments": assignments, "label_map": label_map}


def _classify_single_day(sample: Dict[str, Any], model_centers: List[List[float]]) -> Dict[str, Any]:
    v = np.array([sample.get("ml", 0), sample.get("duracion", 0), sample.get("hour", 12), sample.get("gap", 0)])
    centers = np.array(model_centers)
    dists = np.linalg.norm(centers - v, axis=1)
    idx = int(dists.argmin())
    return {"cluster": idx, "dist": float(dists[idx])}


@router.get("/dashboard/summary")
def dashboard_summary(days: int = Query(7, ge=1, le=30)) -> Dict[str, Any]:
    now_ts = int(time.time())
    state = callbacks.latest_readings
    status = dict(state.get("status") or {})
    raw_last = state.get("raw_last") or {}
    hydration_last = state.get("hydration_last") or {}
    last_event = state.get("last_event") or {}

    last_seen_ts = status.get("last_seen_ts") or raw_last.get("ts") or last_event.get("ts")
    is_online = bool(last_seen_ts and (now_ts - int(last_seen_ts) <= 600))
    is_system_on = is_online

    last_drink_ts = status.get("last_drink_ts") or hydration_last.get("ts") or last_event.get("ts")
    is_drinking = bool(last_drink_ts and (now_ts - int(last_drink_ts) <= 10))

    last_command_raw = state.get("last_command")
    last_command = dict(last_command_raw) if isinstance(last_command_raw, dict) and last_command_raw else None
    if last_command and "ts" in last_command:
        last_command["iso"] = _ts_to_iso(last_command.get("ts"))

    is_filling = False
    if last_command:
        payload = last_command.get("payload") if isinstance(last_command.get("payload"), dict) else None
        cmd = payload.get("command") if isinstance(payload, dict) else None
        cmd_ts = last_command.get("ts")
        if cmd in {"llenar", "fill"} and cmd_ts and now_ts - int(cmd_ts) <= 6:
            is_filling = True

    tank_percent = status.get("tank_level_percent")
    if tank_percent is None:
        tank_percent = last_event.get("tank_percent")
    if tank_percent is None:
        tank_percent = 0.0

    week_package = _hydration_week_with_labels(days)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_entry = next((item for item in week_package.get("items", []) if item.get("date") == today_str), None)

    today_record = db.get_hydration_for_day(today_str) or {"day": today_str, "ml": 0, "updated_ts": None}

    classification_today: Optional[Dict[str, Any]] = None
    centers = (week_package.get("kmeans") or {}).get("centers")
    if centers and today_entry:
        sample = {"ml": today_entry.get("value_ml", 0), "duracion": 0.0, "hour": 12.0, "gap": 0.0}
        classification_today = _classify_single_day(sample, centers)
        classification_today["label"] = today_entry.get("human_label")

    level_counter = Counter(item.get("level") for item in week_package.get("items", []))
    dominant_level = None
    if level_counter:
        dominant_level = level_counter.most_common(1)[0][0]

    summary_text = "Sin datos de hidratación todavía."
    if dominant_level:
        human = {"high": "Adecuado", "medium": "Medio", "low": "Mínimo"}
        summary_text = f"Consumo predominante: {human.get(dominant_level, dominant_level.title())} en los últimos {days} días."
        if level_counter.get("low"):
            summary_text += " Revisa niveles de agua por días con mínimo consumo."

    last_drink_ts = last_drink_ts if last_drink_ts else None

    return {
        "device": {
            "id": None,
            "topic": SUB_TOPIC,
        },
        "status": {
            "is_online": is_online,
            "is_system_on": bool(is_system_on),
            "is_drinking": bool(is_drinking),
            "is_filling": bool(is_filling),
            "tank_level_percent": round(float(tank_percent), 2),
            "last_seen_ts": last_seen_ts,
            "last_seen_iso": _ts_to_iso(last_seen_ts),
        },
        "last_command": last_command,
        "last_drink": {
            "ts": last_drink_ts,
            "iso": _ts_to_iso(last_drink_ts),
            "ml": hydration_last.get("ml_consumed"),
            "volumen_inicio": hydration_last.get("volumen_inicio"),
            "volumen_fin": hydration_last.get("volumen_fin"),
            "duracion": hydration_last.get("duracion"),
        } if last_drink_ts else None,
        "hydration": {
            "today": {
                "day": today_record.get("day"),
                "ml": today_record.get("ml", 0),
                "updated_ts": today_record.get("updated_ts"),
                "entry": today_entry,
                "classification": classification_today,
            },
            "week": week_package,
            "summary": summary_text,
        },
        "last_event": last_event,
        "raw_last": raw_last,
    }


@router.get("/hydration/classify/day")
def classify_day(date: str):
    # retrieve the day's ml
    record = db.get_hydration_for_day(date)
    if not record:
        raise HTTPException(status_code=404, detail="No hydration data for date")

    sample = {"ml": record["ml"], "duracion": 0.0, "hour": 12.0, "gap": 0.0}

    # gather historical hydration_log rows to form events for KMeans
    conn = db.get_conn()
    c = conn.cursor()
    c.execute("SELECT day, ml FROM hydration_log ORDER BY day DESC LIMIT 60")
    rows = c.fetchall()
    events: List[Dict[str, Any]] = []
    for r in rows:
        events.append({"day": r["day"], "ml": r["ml"], "duracion": 0.0, "hour": 12.0, "gap": 0.0})

    if not events:
        raise HTTPException(status_code=400, detail="Not enough historical data")

    km_summary = _run_kmeans(events, n_clusters=3)
    centers = km_summary.get("centers")
    if not centers:
        raise HTTPException(status_code=500, detail="KMeans failed")

    classification = _classify_single_day(sample, centers)
    return {"date": date, "sample": sample, "classification": classification, "kmeans": km_summary}

