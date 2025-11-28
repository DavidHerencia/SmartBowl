from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]

# MQTT
MQTT_HOST: str = os.getenv("MQTT_HOST", "n2721c42.ala.us-east-1.emqxsl.com")
MQTT_PORT: int = int(os.getenv("MQTT_PORT", "8883"))
MQTT_USER: str | None = os.getenv("MQTT_USER")
MQTT_PASS: str | None = os.getenv("MQTT_PASS")
MQTT_KEEPALIVE: int = int(os.getenv("MQTT_KEEPALIVE", "60"))

# For a simplified flow we'll use a single inbound topic where the ESP32 sends
# a JSON payload containing hydration and sensor info. Default below can be
# overridden via env.
SUB_TOPIC: str = os.getenv("SUB_TOPIC", "home/water/consumption")

# Single outbound topic for actuator commands; payloads will be JSON like
# { "command": "llenar" } or similar.
PUB_TOPIC: str = os.getenv("PUB_TOPIC", "home/actions")

# Database
DB_PATH: str = os.getenv("DB_PATH", str(ROOT / "smartbowl.db"))

DEFAULT_QOS: int = int(os.getenv("DEFAULT_QOS", "1"))
