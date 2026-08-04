# Prueba integral: Mi pasillo + sitio simulado

## Resultado preparado

La aplicación ofrece dos sitios independientes:

- `pasillo-real`: cámara Dell WB7022, calibración guardada, tablas blancas como objeto fijo y tres áreas métricas.
- `sitio-simulado`: conserva el mapa comercial, 900 recorridos y todo su historial simulado.

Cambiar de sitio sustituye mapa, áreas, objetos, trayectorias, conteos y mapa de calor. Los datos nunca se mezclan.

## Áreas del pasillo

| areaId | Nombre | Uso | Límites aproximados en metros |
|---|---|---|---|
| `zona-cercana` | Zona cercana | Acceso frente a cámara | X 0.05–1.65, Y 0.00–0.90 |
| `zona-media` | Zona media | Tránsito central | X 0.18–1.62, Y 0.90–2.25 |
| `zona-lejana` | Zona lejana | Fondo del pasillo | X 0.35–1.62, Y 2.25–4.50 |

La precisión es deliberadamente aproximada para la presentación. La cámara y las tablas blancas deben permanecer inmóviles.

## Arranque

1. Inicia Flask con la cámara Dell en `http://0.0.0.0:5000`.
2. Verifica `http://127.0.0.1:5000/api/v1/sites`.
3. La PC y el Android deben estar en la misma red Wi‑Fi.
4. En `.env.local`, establece la IP LAN actual de la PC:

   `EXPO_PUBLIC_API_BASE_URL=http://192.168.1.79:5000`

5. Abre `iniciar-visioflow.bat`, elige LAN y escanea el QR con Expo Go.
6. Inicia sesión con `operador` / `visioflow`.
7. Pulsa `Cambiar a Mi pasillo · en vivo`.

Si cambia la red o la IP de la PC, actualiza solamente `.env.local` y reinicia Expo.

## Prueba en vivo

1. Deja el pasillo vacío durante cinco segundos: los tres conteos deben mostrar cero.
2. Una persona camina desde el fondo hacia la cámara.
3. Deben cambiar, en orden, `Zona lejana`, `Zona media` y `Zona cercana`.
4. El mapa muestra el tracker y conserva cada punto de la última hora.
5. Selecciona `Mapa de calor`; la superficie se acumula donde pasó la persona.
6. Alterna `Vista superior` / `Vista 3D`.
7. Cambia a `Sitio simulado`: reaparecen su mapa, mobiliario, estadísticas e historial originales.
8. Vuelve a `Mi pasillo`: se recuperan las áreas y lecturas exclusivas del pasillo.

## API sencilla usada por la app

- `GET /api/v1/sites`
- `GET /api/v1/sites/pasillo-real/bootstrap`
- `GET /api/v1/sites/pasillo-real/track-points?limit=12000`
- `GET /api/v1/sites/pasillo-real/area-state`

El frontend consulta puntos y conteos cada segundo. Cada punto preserva simultáneamente `imagePoint.u/v` en píxeles y `x/y/z` en metros, además de `cameraId`, `sessionId`, `frameId`, `trackerId`, `capturedAt`, `areaId` y `confidence`.

La implementación de demostración mantiene hasta 12,000 puntos en memoria. El servidor definitivo debe persistir exactamente las mismas formas en las tablas ya definidas en `database/schema.sql`.
