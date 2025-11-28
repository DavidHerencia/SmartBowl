## SmartBowl – Arquitectura, flujo de datos y analítica

Este proyecto implementa un bebedero inteligente para mascotas con:

- **ESP32 + sensores** que miden volumen de agua antes y después de una presencia.
- **Backend FastAPI** que recibe eventos vía MQTT, los guarda en SQLite y calcula analíticas (incluyendo K-Means).
- **Frontend React** que muestra el estado en tiempo real, historial y clusters de consumo.

La lógica de detección de presencia y cálculo de volumen en el bowl vive en el **firmware del ESP32**. El backend asume que ya recibe esos valores calculados y se enfoca en almacenar, analizar y exponer la información.

---

## 1. Flujo de datos de extremo a extremo

### 1.1. Publicación desde el ESP32 (MQTT)

Cada vez que la mascota bebe, el ESP32 publica un mensaje JSON en el tópico de entrada (por defecto `home/water/consumption`):

```json
{
	"volumen_inicio": 950.0,
	"volumen_fin": 820.5,
	"duracion": 18.4
}
```

Semántica de los campos (definidos en el ESP32):

- `volumen_inicio`: volumen en ml justo antes de que la mascota empiece a beber.
- `volumen_fin`: volumen en ml después del consumo.
- `duracion`: duración del evento de presencia/consumo en segundos.

### 1.2. Recepción en el backend (MQTT → callbacks)

Archivo clave: `backend/app/mqtt/callbacks.py`.

1. El cliente MQTT (`MQTTClient` en `app/mqtt/client.py`) se conecta al broker usando TLS y credenciales del `.env`.
2. En `on_connect`, se suscribe al tópico `SUB_TOPIC` (por defecto `home/water/consumption`).
3. En `on_message`, cada payload se intenta parsear como JSON.
4. Si el JSON tiene las 3 llaves obligatorias (`volumen_inicio`, `volumen_fin`, `duracion`), se procesa como **evento de hidratación** llamando a `_handle_hydration_event`.
5. Si no cumple, solo se guarda como lectura cruda; esto permite debug y otros sensores.

### 1.3. Procesamiento de un evento de hidratación

En `_handle_hydration_event` ocurre la lógica interesante:

1. **Parseo y validación**
	 - Convierte los campos a `float` (ml y segundos).
	 - Si hay errores de formato, se ignora el evento como hidratación pero se guarda crudo.

2. **Cálculo del consumo**
	 - \( \text{ml_consumed} = \max(0, vi - vf) \)
	 - Representa cuánta agua tomó la mascota en ese evento.

3. **Cálculo del gap entre eventos**
	 - Usa `_previous_event_ts` para medir cuántos minutos pasaron desde el último evento: `gap_min`.
	 - Esto sirve para saber si la mascota está bebiendo muy seguido o muy poco.

4. **Estimación de capacidad del bowl**
	 - Lleva un `_estimated_capacity_ml` que se va actualizando con el mayor `vi` visto.
	 - Esto permite aproximar la **capacidad total del tanque** sin hardcodearla.

5. **Nivel del tanque en porcentaje**
	 - Si conoce la capacidad aproximada, calcula:
	 - \( \text{tank\_percent} = \frac{vf}{\text{capacidad}} \times 100 \)
	 - Acotado entre 0 y 100.

6. **Actualización de estado en memoria** (`latest_readings`)
	 - Guarda `hydration_last` con:
		 - `ts`, `volumen_inicio`, `volumen_fin`, `duracion`, `ml_consumed`, `gap_min`, `tank_percent`.
	 - Actualiza `status`:
		 - `last_seen_ts`, `estimated_capacity_ml`, `tank_level_percent`, `last_drink_ts`, `last_drink_ml`.
	 - Actualiza `last_event` para que los endpoints la puedan exponer.

7. **Persistencia en SQLite**
	 - Llama a `db.save_hydration_event(...)` para guardar el evento completo.
	 - Calcula el día UTC y actualiza `hydration_log` vía `db.upsert_daily_ml(day, ml_consumed)` sumando lo bebido en ese día.
	 - Guarda también el mensaje crudo en la tabla `readings` para trazabilidad.

### 1.4. Agregación diaria y semanal

El módulo `backend/app/core/db.py` define:

- `hydration_events`: tabla con cada evento detallado.
- `hydration_log`: tabla con consumo agregado diario (`day`, `ml`, `updated_ts`).

Funciones útiles:

- `get_hydration_for_day(day)`: devuelve ml totales para una fecha.
- `get_hydration_days(limit)`: últimos días con consumo.

Esto permite que los endpoints de analítica construyan series de tiempo y entren los modelos sin recalcular todo cada vez.

---

## 2. K-Means: cómo se usa y qué aporta

Archivo clave: `backend/app/api/analytics.py`.

### 2.1. ¿Qué problema resuelve?

El objetivo es **descubrir patrones de hidratación** y marcar días como:

- "Adecuado": consumo normal / saludable.
- "Medio": algo por debajo o por encima de lo habitual.
- "Mínimo": consumo muy bajo (posible riesgo: el bowl no tiene agua o la mascota no está bebiendo).

En vez de fijar umbrales estáticos (ej. "< 200 ml"), usamos K-Means para **aprender esos grupos directamente de los datos reales** del animal.

### 2.2. Preparación de features

Función: `_prepare_features(events)`.

Cada día se representa como un vector numérico \(x \in \mathbb{R}^4\):

- `ml` – consumo total del día en mililitros.
- `duracion` – duración total o promedio de los eventos (aquí se usa 0.0 en el agregado simple, pero está listo para extenderse).
- `hour` – hora promedio del consumo (también se puede extender para tener hábitos diurnos/nocturnos).
- `gap` – tiempo entre eventos (se puede usar para detectar consumo muy espaciado).

Estos valores se empaquetan en una matriz \(X \in \mathbb{R}^{n \times 4}\) donde cada fila es un día.

### 2.3. Entrenamiento de K-Means

Función: `_run_kmeans(events, n_clusters=3)`.

1. Construye `X` con los vectores de características.
2. Ejecuta `KMeans` de scikit-learn con 3 clusters (o menos si hay pocos días).
3. Obtiene:
	 - `centers`: centroide de cada cluster (vector promedio de \[ml, duracion, hour, gap]).
	 - `labels`: asignación de cada día a un cluster.

### 2.4. Mapear clusters a etiquetas humanas

Después de entrenar, los clusters no tienen significado humano; solo son índices (0, 1, 2). Para hacerlos útiles:

1. Ordena los clusters por el primer componente del centro (ml) de mayor a menor.
2. Asigna etiquetas en este orden:
	 - Cluster con mayor ml → `"Adecuado"`.
	 - Siguiente → `"Medio"`.
	 - Último → `"Mínimo"`.

Esto se guarda en `label_map` y se devuelve junto con los centros.

### 2.5. Clasificar cada día y el día actual

- `_hydration_week_with_labels(days)` arma los últimos `days` días, corre K-Means y devuelve:
	- `items`: para cada día →
		- `day`, `date`, `value_ml`, `level` (`high|medium|low`), `human_label`, `cluster`.
	- `kmeans`: con `centers`, `assignments` y `label_map`.

- `_classify_single_day(sample, model_centers)` toma un vector nuevo (por ejemplo el día de hoy) y busca el centroide más cercano usando distancia Euclídea:

	$$ \text{dist}(v, c_i) = \lVert v - c_i \rVert_2 $$

	Devuelve:
	- `cluster`: índice del centro más cercano.
	- `dist`: qué tan lejos está (útil como grado de anomalía).

### 2.6. Cómo se usa en el dashboard

En el endpoint `GET /analytics/dashboard/summary`:

1. Llama a `_hydration_week_with_labels(days)` para obtener:
	 - Serie semanal con etiquetas `Adecuado/Medio/Mínimo`.
	 - Centros y asignaciones de K-Means.
2. Identifica el día de hoy y obtiene su registro en `hydration_log`.
3. Usa `_classify_single_day` para ver en qué cluster cae hoy y qué tan lejos está del centro.
4. Devuelve esta info al frontend, que la muestra como:
	 - Tarjetas de colores por día (heatmap de hidratación).
	 - Resumen de consumo predominante.
	 - Clusters con valores promedio (ml, duración, hora).

Beneficio para el usuario final:

- No solo ve cuánto tomó hoy su mascota, sino **cómo se compara con su patrón típico**.
- Es más robusto que un umbral fijo, porque se adapta al propio historial del animal.
- Permite detectar **anomalías**: días que caen lejos del centro del cluster esperado (por ejemplo, casi sin agua o mucho más de lo normal).

---

## 3. Endpoints principales del backend

### 3.1. Salud

- `GET /` → `{ "msg": "SmartBowl API root" }`
- `GET /health/` → `{ "msg": "SmartBowl API running" }`
- `GET /health/ready` →
	```json
	{
		"ok": true,
		"mqtt_thread_alive": true
	}
	```
	Verifica conexión a la base de datos y estado del hilo MQTT.

### 3.2. Sensores (`/sensors`)

- `GET /sensors/latest`
	- Devuelve la última lectura cruda y derivada, incluyendo:
	```json
	{
		"subscribed_topic": "home/water/consumption",
		"raw_last": { "topic": "...", "raw": "...", "parsed": {"..."}, "ts": 1234567890 },
		"hydration_last": {
			"ts": 1234567890,
			"volumen_inicio": 950.0,
			"volumen_fin": 820.5,
			"duracion": 18.4,
			"ml_consumed": 129.5,
			"gap_min": 42.0,
			"tank_percent": 75.3
		},
		"status": {
			"last_seen_ts": 1234567890,
			"estimated_capacity_ml": 980.0,
			"tank_level_percent": 75.3,
			"last_drink_ts": 1234567890,
			"last_drink_ml": 129.5
		},
		"last_event": { "...": "igual que hydration_last" },
		"last_command": { "topic": "home/actions", "payload": {"command": "llenar"}, "ts": 1234567890 }
	}
	```

- `GET /sensors/raw?limit=N`
	- Últimos `N` mensajes crudos de MQTT, con payload parseado si es JSON.

- `GET /sensors/topic?topic=...`
	- Última lectura para un tópico específico (cache o DB).

### 3.3. Actuadores (`/actuators`)

- `POST /actuators`
	- Body:
	```json
	{ "command": "llenar" }
	```
	- Publica ese JSON en `home/actions` vía MQTT.
	- Actualiza `latest_readings["last_command"]` y marca `status["is_filling"] = true` si el comando es `llenar`.
	- Respuesta:
	```json
	{
		"topic": "home/actions",
		"payload": { "command": "llenar" },
		"status": "published",
		"ts": 1234567890
	}
	```

### 3.4. Analítica / Hidratación (`/analytics`)

- `GET /analytics/hydration/today`
	- Devuelve el consumo total del día actual desde `hydration_log`.

- `GET /analytics/hydration/week?days=7`
	- Lista bruta de los últimos `days` días con `day`, `ml`, `updated_ts`.

- `GET /analytics/dashboard/summary?days=14`
	- Endpoint principal que alimenta el frontend. Estructura simplificada:
	```json
	{
		"device": { "id": null, "topic": "home/water/consumption" },
		"status": {
			"is_online": true,
			"is_system_on": true,
			"is_drinking": false,
			"is_filling": false,
			"tank_level_percent": 72.5,
			"last_seen_ts": 1234567890,
			"last_seen_iso": "2025-11-28T15:20:10Z"
		},
		"last_command": { "topic": "home/actions", "payload": {"command": "llenar"}, "ts": 1234567800, "iso": "2025-11-28T15:20:00Z" },
		"last_drink": {
			"ts": 1234567890,
			"iso": "2025-11-28T15:20:10Z",
			"ml": 130.0,
			"volumen_inicio": 950.0,
			"volumen_fin": 820.0,
			"duracion": 18.4
		},
		"hydration": {
			"today": {
				"day": "2025-11-28",
				"ml": 780,
				"updated_ts": 1234567890,
				"entry": { "date": "2025-11-28", "value_ml": 780, "level": "medium", "human_label": "Medio", "cluster": 1 },
				"classification": { "cluster": 1, "dist": 0.42, "label": "Medio" }
			},
			"week": {
				"items": [
					{ "day": "Lun", "date": "2025-11-24", "value_ml": 850, "level": "high", "human_label": "Adecuado", "cluster": 0 },
					{ "day": "Mar", "date": "2025-11-25", "value_ml": 200, "level": "low", "human_label": "Mínimo", "cluster": 2 }
				],
				"kmeans": {
					"centers": [[900, 0, 12, 0], [500, 0, 12, 0], [150, 0, 12, 0]],
					"assignments": [{ "day": "2025-11-24", "cluster": 0, "label": "Adecuado" }],
					"label_map": { "0": "Adecuado", "1": "Medio", "2": "Mínimo" }
				}
			},
			"summary": "Consumo predominante: Medio en los últimos 14 días. Revisa niveles de agua por días con mínimo consumo."
		},
		"last_event": { "...": "último evento procesado" },
		"raw_last": { "...": "último mensaje crudo" }
	}
	```

- `GET /analytics/hydration/classify/day?date=YYYY-MM-DD`
	- Reconstruye un modelo K-Means a partir de ~60 días de historial y clasifica ese día concreto.

---

## 4. Cómo explicarlo al profesor y venderlo al usuario final

### 4.1. Explicación técnica (para el profesor)

1. **Arquitectura desacoplada**: el ESP32 solo se preocupa de sensar y publicar tres números. El backend se encarga de persistencia, agregación y ML. El frontend consume una sola API (`/analytics/dashboard/summary`) pensada para UI.
2. **Procesamiento por eventos**: cada mensaje MQTT se traduce en:
	 - Un registro crudo (`readings`).
	 - Un evento enriquecido con consumo, gap y nivel del tanque.
	 - Una actualización incremental del log diario. 
3. **K-Means sobre historial**: el modelo no es global; se entrena sobre el historial de esa mascota, adaptando los clusters a su patrón real de hidratación.
4. **Clasificación y scoring**: para cada día, y en particular hoy, se calcula a qué cluster pertenece y qué tan lejos está del centro, lo que permite interpretar el resultado como "día típico", "ligeramente atípico" o "muy raro".
5. **Todo en SQLite + FastAPI**: fácil de depurar y portable, pero con conceptos que se pueden escalar a otras bases y brokers.

### 4.2. Mensaje para el usuario final (vender el producto)

- **Más que un dispensador automático**: SmartBowl no solo llena el bebedero; aprende el patrón de hidratación de tu mascota.
- **Alertas tempranas**: cuando un día se parece al cluster "Mínimo" (muy poco consumo), el sistema puede advertirte para revisar si falta agua o si tu mascota podría estar enferma.
- **Visualización clara**: el dashboard muestra un mapa de calor semanal y resúmenes tipo "Adecuado / Medio / Mínimo", mucho más fáciles de entender que números sueltos.
- **Adaptativo**: los umbrales no son fijos; el sistema se ajusta automáticamente al tamaño de tu mascota, su raza, clima, etc., porque aprende de su propio historial.
- **Histórico utilizable**: toda la data queda guardada y se puede compartir con un veterinario para analizar cambios en el consumo a lo largo del tiempo.

En resumen, el uso de K-Means convierte simples lecturas de sensor en **insights accionables**: ayuda a detectar comportamientos anómalos de hidratación y aporta una capa de inteligencia que diferencia al producto de un bebedero automático tradicional.

