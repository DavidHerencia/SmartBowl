from __future__ import annotations
import time
from fastapi import APIRouter, Body, HTTPException
from typing import Dict, Any
from ..mqtt.client import mqtt_client
from ..core.config import PUB_TOPIC
import json
from ..mqtt import callbacks

router = APIRouter(prefix="/actuators", tags=["actuators"])


@router.post("/")
def publish_command(payload: Dict[str, Any] = Body(..., example={"command": "llenar"})):
    """Publica cualquier comando JSON en el tópico `home/actions`.

    El body es directamente el mensaje que se enviará al MQTT, se espera
    al menos la llave `command` para que el firmware del bowl lo reconozca.
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be a JSON object")
    if "command" not in payload:
        raise HTTPException(status_code=400, detail="payload must include 'command'")

    message = json.dumps(payload)
    mqtt_client.publish(PUB_TOPIC, message)
    ts = int(time.time())
    callbacks.latest_readings["last_command"] = {"topic": PUB_TOPIC, "payload": payload, "ts": ts}
    status = callbacks.latest_readings.setdefault("status", {})
    status["last_command_ts"] = ts
    status["last_command"] = payload
    if payload.get("command") in {"llenar", "fill"}:
        status["is_filling"] = True

    return {"topic": PUB_TOPIC, "payload": payload, "status": "published", "ts": ts}
