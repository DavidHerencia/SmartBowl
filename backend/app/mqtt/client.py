from __future__ import annotations
import threading
import time
import ssl
import paho.mqtt.client as mqtt
from typing import Callable, Optional
from ..core.config import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS, MQTT_KEEPALIVE
from . import callbacks


class MQTTClient:
    def __init__(self) -> None:
        self._client = mqtt.Client()
        # try to enable TLS; if broker uses 8883 it's expected
        try:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        except Exception as e:
            print("Warning: tls_set failed:", e)

        if MQTT_USER:
            self._client.username_pw_set(MQTT_USER, MQTT_PASS)

        # assign callbacks
        self._client.on_connect = callbacks.on_connect
        self._client.on_message = callbacks.on_message

        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        def _run():
            backoff = 1
            while True:
                try:
                    print("Trying MQTT connect to", MQTT_HOST, MQTT_PORT)
                    self._client.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)
                    self._client.loop_forever()
                except Exception as e:
                    print("MQTT connection error:", e)
                    time.sleep(backoff)
                    backoff = min(30, backoff * 2)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        self._running = True

    def publish(self, topic: str, message: str, qos: int = 1, retain: bool = False):
        return self._client.publish(topic, payload=message, qos=qos, retain=retain)


mqtt_client = MQTTClient()
