from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from .api import sensors, actuators, analytics, health
from .mqtt import client as mqtt_client

app = FastAPI(title="SmartBowl API (MQTT bridge)")


def _load_cors_origins() -> list[str]:
    env_value = os.getenv("API_ALLOWED_ORIGINS")
    if env_value:
        return [origin.strip() for origin in env_value.split(",") if origin.strip()]
    # sensible defaults for local development
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sensors.router)
app.include_router(actuators.router)
app.include_router(analytics.router)


@app.on_event("startup")
def startup_event():
    # start mqtt client background thread
    mqtt_client.mqtt_client.start()
    print("Startup complete: MQTT client started")


@app.get("/")
def root():
    return {"msg": "SmartBowl API root"}
