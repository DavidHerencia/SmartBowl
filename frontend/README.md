# SmartBowl Frontend

Dashboard React para visualizar en tiempo real el estado del bebedero inteligente y las analíticas generadas por el backend FastAPI.

## Características

- **Panel en vivo** con estado del dispositivo, nivel del tanque, último consumo y detección de actividad.
- **Acciones rápidas** para enviar comandos MQTT al backend (`llenar`, `encender`, `apagar`).
- **Heatmap semanal** con las etiquetas aprendidas por K-Means (Adecuado, Medio, Mínimo).
- **Telemetría cruda** mostrando el último payload MQTT, gap entre eventos y distancia a los clusters.
- **Auto-refresh** cada 8 segundos + botón manual de actualización.
- Construido con **Vite + React + TailwindCSS** y componentes reutilizables.

## Requisitos

- Node.js 18+ (recomendado 20+).
- Backend SmartBowl corriendo (por defecto en `http://localhost:8000`).

## Variables de entorno

Crear un archivo `.env` en esta carpeta (opcional) con:

```
VITE_API_BASE_URL=http://localhost:8000
```

Si no se define, se usa `http://localhost:8000` por defecto.

## Scripts disponibles

```bash
npm install        # instala dependencias
npm run dev        # modo desarrollo en http://localhost:5173
npm run build      # compila para producción en dist/
npm run preview    # sirve la build generada
```

## Flujo recomendado

1. Instalar dependencias y levantar el backend (FastAPI + MQTT + SQLite).
2. Ejecutar `npm run dev` para trabajar con hot reload.
3. Ajustar `VITE_API_BASE_URL` si el backend está en otra máquina o puerto.
4. Usar `npm run build && npm run preview` para validar la build final.

## Notas

- El botón **Llenar tanque** publica `{ "command": "llenar" }` al endpoint `/actuators` del backend.
- El botón de encendido/apagado envía comandos `encender` y `apagar` (pueden ignorarse si el firmware no los usa, pero quedan registrados en la API).
- El heatmap utiliza los datos devueltos por `GET /analytics/dashboard/summary` y se actualiza automáticamente.
