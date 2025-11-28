# # main.py
# import os
# import threading
# import time
# import sqlite3
# from typing import Dict, Any

# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# import paho.mqtt.client as mqtt
# from dotenv import load_dotenv

# load_dotenv()  # lee .env si existe

# # ---------- Config (desde ENV) ----------
# MQTT_HOST = os.getenv("MQTT_HOST", "n2721c42.ala.us-east-1.emqxsl.com")
# MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
# MQTT_USER = os.getenv("MQTT_USER", "admin")
# MQTT_PASS = os.getenv("MQTT_PASS", "1234")
# MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))

# SUB_TOPIC = os.getenv("SUB_TOPIC", "home/water/consumption")
# PUB_TOPIC_PREFIX = os.getenv("PUB_TOPIC_PREFIX", "home/actions")

# DB_PATH = os.getenv("DB_PATH", "smartbowl.db")

# # ---------- App & Storage ----------
# app = FastAPI(title="SmartBowl API (MQTT bridge)")

# # In-memory store of latest sensor values (thread-safe)
# _latest_lock = threading.Lock()
# _latest: Dict[str, Dict[str, Any]] = {}

# # ---------- Simple SQLite persistence ----------
# def init_db():
#     conn = sqlite3.connect(DB_PATH, check_same_thread=False)
#     c = conn.cursor()
#     c.execute(
#         """
#         CREATE TABLE IF NOT EXISTS readings (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             topic TEXT NOT NULL,
#             payload TEXT NOT NULL,
#             ts INTEGER NOT NULL
#         )
#         """
#     )
#     conn.commit()
#     return conn

# db_conn = init_db()

# def save_reading(topic: str, payload: str):
#     ts = int(time.time())
#     c = db_conn.cursor()
#     c.execute("INSERT INTO readings (topic, payload, ts) VALUES (?, ?, ?)", (topic, payload, ts))
#     db_conn.commit()

# # ---------- MQTT callbacks ----------
# def on_connect(client, userdata, flags, rc):
#     print("MQTT connected, rc=", rc)
#     # subscribe on connect
#     client.subscribe(SUB_TOPIC)
#     print("Subscribed to", SUB_TOPIC)

# def on_message(client, userdata, msg):
#     payload = msg.payload.decode("utf-8", errors="ignore")
#     topic = msg.topic
#     ts = int(time.time())

#     # store in-memory latest
#     with _latest_lock:
#         _latest[topic] = {"payload": payload, "ts": ts}

#     # persist
#     try:
#         save_reading(topic, payload)
#     except Exception as e:
#         print("DB save error:", e)

#     print(f"MQTT msg: {topic} -> {payload}")

# # ---------- MQTT client setup ----------
# mqtt_client = mqtt.Client()

# # Use TLS by default for cloud brokers on 8883
# try:
#     mqtt_client.tls_set()  # uses system CA certs
# except Exception as e:
#     print("Warning: tls_set() failed:", e)

# mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
# mqtt_client.on_connect = on_connect
# mqtt_client.on_message = on_message

# def mqtt_connect_loop():
#     """Run in background thread: connect and keep loop running."""
#     backoff = 1
#     while True:
#         try:
#             print("Trying MQTT connect to", MQTT_HOST, MQTT_PORT)
#             mqtt_client.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)
#             mqtt_client.loop_forever()  # blocking until disconnect
#         except Exception as e:
#             print("MQTT connection error:", e)
#             print(f"Reconnecting in {backoff}s...")
#             time.sleep(backoff)
#             backoff = min(30, backoff * 2)

# mqtt_thread: threading.Thread | None = None

# # ---------- FastAPI endpoints ----------
# class ActuatorCmd(BaseModel):
#     topic: str | None = None  # if None, use prefix + given name
#     message: str
#     qos: int = 1
#     retain: bool = False

# @app.on_event("startup")
# def startup_event():
#     global mqtt_thread
#     # Start MQTT client in background thread
#     if mqtt_thread is None:
#         mqtt_thread = threading.Thread(target=mqtt_connect_loop, daemon=True)
#         mqtt_thread.start()
#     print("API startup complete. MQTT background thread started.")

# @app.get("/")
# def root():
#     return {"msg": "SmartBowl API running"}

# @app.get("/sensors")
# def list_latest():
#     """Return latest readings (topic -> payload, ts)."""
#     with _latest_lock:
#         # copy to avoid race
#         data = {k: v.copy() for k, v in _latest.items()}
#     return {"latest": data}

# @app.get("/sensors/raw")
# def last_n_readings(limit: int = 50):
#     """Return last `limit` readings from DB (most recent first)."""
#     c = db_conn.cursor()
#     c.execute("SELECT topic, payload, ts FROM readings ORDER BY id DESC LIMIT ?", (limit,))
#     rows = c.fetchall()
#     return {"count": len(rows), "rows": [{"topic": r[0], "payload": r[1], "ts": r[2]} for r in rows]}

# @app.get("/sensors/topic")
# def get_topic(topic: str):
#     """Return last value for a specific topic (exact match)."""
#     with _latest_lock:
#         v = _latest.get(topic)
#     if not v:
#         raise HTTPException(status_code=404, detail="Topic not found in latest cache")
#     return {"topic": topic, "payload": v["payload"], "ts": v["ts"]}

# @app.post("/actuator/publish")
# def publish_cmd(cmd: ActuatorCmd):
#     # determine topic
#     topic = cmd.topic if cmd.topic else PUB_TOPIC_PREFIX
#     # publish
#     try:
#         mqtt_client.publish(topic, cmd.message, qos=cmd.qos, retain=cmd.retain)
#         return {"status": "published", "topic": topic, "message": cmd.message}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
