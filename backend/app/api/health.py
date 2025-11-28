from __future__ import annotations
from fastapi import APIRouter
from ..mqtt import client as mqtt_client

router = APIRouter(tags=["health"])


@router.get("/")
def root():
    return {"msg": "SmartBowl API running"}


@router.get("/ready")
def ready():
    # very simple readiness check: DB connection and MQTT thread existence
    ok = True
    try:
        from ..core.db import get_conn

        _ = get_conn()
    except Exception:
        ok = False
    mqtt_thread_alive = mqtt_client.mqtt_client._thread is None or mqtt_client.mqtt_client._thread.is_alive()
    return {"ok": ok, "mqtt_thread_alive": mqtt_thread_alive}
