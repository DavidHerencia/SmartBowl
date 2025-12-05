# SmartBowl Backend

Backend for SmartBowl — a smart pet water bowl. Built with FastAPI, paho-mqtt and SQLite. Includes light ML clustering using scikit-learn KMeans to classify daily hydration.

Structure (key files):

- `app/main.py` - FastAPI application entry.
- `app/mqtt/client.py` - MQTT client wrapper (background thread).
- `app/mqtt/callbacks.py` - message callbacks: persist readings and hydration events.
- `app/api/*` - routers for sensors, actuators, analytics, health.
- `app/core/db.py` - sqlite helpers and schema.
- `scripts/seed_db.py` - simple script to populate DB with mock data.


Run locally:

1. Install deps: `uv sync`
2. Seed DB con datos de ejemplo (recomendado para dashboards):

	```bash
	python scripts/seed_db.py
	```

	Genera mediciones históricas para alimentar el clustering K-Means.
3. Start server locally (using Uvicorn):

Permite el acceso CORS desde el frontend configurando `API_ALLOWED_ORIGINS`, por ejemplo:

```bash
uv run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000   
```

MQTT topics (defaults are configurable via env vars):

- `home/smartbowl/data` — single inbound topic where the ESP32 posts a JSON payload that includes hydration info. Expected example payload:

	{
		"volumen_inicio": 950.0,
		"volumen_fin": 920.5,
		"duracion": 12.5
	}

- `home/water/level` — tópico adicional para reportar el volumen actual del tanque cuando se rellena o se mide manualmente. Payload típico:

	{
		"volumen": 720.0
	}

- `home/actions` — single outbound topic where the backend publishes actuator commands as JSON, e.g. `{ "command": "llenar", "actuator": "bomba" }`.

Endpoints examples:

- `GET /sensors/latest`
- `GET /sensors/topic?topic=smartbowl/sensores/nivel`
- `POST /actuators` body `{ "command": "llenar" }`
- `GET /analytics/hydration/today`
- `GET /analytics/hydration/classify/day?date=2025-11-28`
- `GET /analytics/dashboard/summary`

Docker: build with `docker build -t smartbowl .` and run mapping port 8000.
# SmartBowl Backend
