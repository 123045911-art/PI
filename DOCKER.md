# Visio Flow con Docker Compose

## Arranque

En la raíz del repositorio:

```bash
docker compose up --build
```

- **PostgreSQL:** `localhost:5434` (usuario `admin`, base `visio_flow`; `init.sql` se aplica en el primer arranque con volumen vacío).
- **FastAPI:** http://localhost:8000 (documentación: `/docs`).
- **Flask:** http://localhost:5000

Flask llama a la API por la red interna `http://api:8000` (variables `API_BASE_URL` / `VISIOFLOW_API_BASE_URL`).

## Cámara / vídeo

En Docker el acceso a la webcam del host no está mapeado por defecto. En **Linux** puedes añadir en `docker-compose.yml` bajo el servicio `flask`:

```yaml
devices:
  - /dev/video0:/dev/video0
```

y ajustar el índice de cámara en `TrackerService` si hace falta. En Windows/Mac suele usarse otra estrategia (IP camera, archivo de vídeo, etc.); la app seguirá arrancando aunque no haya dispositivo (mensaje de “No hay video” en el stream).
