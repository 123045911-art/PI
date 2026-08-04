# VisioFlow

VisioFlow combina un contador de personas Flask (OpenCV, YOLOv8 y DeepSORT),
una API FastAPI, PostgreSQL y una aplicación móvil interactiva (Expo Go / React Native). El modulo Flask tambien
ofrece calibracion metrica, escaneo previo de una escena fija y posiciones en
vivo sobre el plano del suelo.

El sistema **no** realiza reconocimiento facial, biometría ni identidad real.
`trackerId` es un identificador temporal de DeepSORT. Tampoco genera ventas ni
datos que el sensor no pueda observar. No se guardan imagenes o video por
defecto; solo JSON de calibracion/escena y el CSV de eventos heredado.

## Modos

Configure `SENSOR_MODE` en `.env`:

| Modo | Fuente | Capacidad metrica |
|---|---|---|
| `rgbd` | RGB y mapa de profundidad alineado | Desproyeccion 3D por pixel; requiere un adaptador del SDK del sensor que entregue el mapa al `RGBDDepthProvider`. |
| `stereo` | Par calibrado, rectificado y baseline conocido | Disparidad SGBM y profundidad; reporta zonas invalidas. |
| `monocular` | Camara RGB normal | Solo X,Y para puntos confirmados sobre el plano calibrado del suelo. No infiere altura ni profundidad general. |

El proveedor OpenCV incluido entrega color. Una camara RGB-D concreta (RealSense,
Azure Kinect, ZED u otra) necesita un adaptador de su SDK que llame
`RGBDDepthProvider.update_depth_map()` con profundidad en metros alineada al RGB.
El escaneo se bloquea en modo RGB-D si ese mapa no existe.

## Sistemas de coordenadas

Cada JSON identifica su sistema:

- Imagen: `(u,v)` en pixeles, origen arriba a la izquierda.
- Camara: `(Xc,Yc,Zc)` en metros; X derecha, Y abajo, Z hacia delante.
- Mundo/suelo: `(X,Y,Z)` en metros; X derecha, Y hacia delante, Z arriba.
  Por defecto el origen es la proyeccion de la camara sobre el suelo.

Para profundidad `d`:

```text
Xc = (u - cx) * d / fx
Yc = (v - cy) * d / fy
Zc = d
P_world = R_camera_to_world * P_camera + t_camera_to_world
```

En monocular, exclusivamente para un punto sobre el suelo:

```text
[X', Y', W'] = H_image_to_ground * [u, v, 1]
X = X' / W'
Y = Y' / W'
Z = 0
```

No se aplica la homografia a puntos suspendidos. La posicion de una persona usa
el contacto aproximado de los pies:

```text
foot_u = (bbox_left + bbox_right) / 2
foot_v = bbox_bottom
```

## Instalacion Flask

```powershell
cd contador_personas_flask
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item ..\.env.example ..\.env
```

Defina al menos `FLASK_SECRET_KEY`. Para la pila completa, complete tambien las
credenciales de PostgreSQL, FastAPI, Redis y la cuenta de servicio. Inicie Flask:

```powershell
python run.py
```

O la pila completa:

```powershell
docker compose up --build
```

- Conteo existente: <http://localhost:5000/>
- Calibracion/escena: <http://localhost:5000/configuration>
- FastAPI: <http://localhost:8000/>

## Imprimir y medir ChArUco

Los valores predeterminados son `DICT_5X5_100`, 7×5 cuadros, cuadro de 0.04 m y
marcador de 0.02 m. Genere el tablero con OpenCV usando exactamente esos datos,
imprima al 100 % (sin "ajustar a pagina") y mida con regla o calibrador el lado
del cuadro impreso. Si no coincide, cambie `CHARUCO_SQUARE_LENGTH_METERS` y
`CHARUCO_MARKER_LENGTH_METERS` por las medidas reales antes de capturar.

Ejemplo de generacion:

```python
import cv2
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)
board = cv2.aruco.CharucoBoard((7, 5), 0.04, 0.02, dictionary)
cv2.imwrite("charuco.png", board.generateImage((1400, 1000), marginSize=40))
```

Capture cinco o mas vistas que cubran centro, bordes, inclinaciones y distancias
distintas. La solucion se rechaza si el RMS excede
`MAX_REPROJECTION_ERROR_PX`. Recalibre si cambia resolucion, enfoque, zoom o la
optica.

## Calibrar el mundo

Despues de los intrinsecos, mida cuatro o mas puntos no colineales del suelo y
sus pixeles. En `/configuration`, edite el JSON de correspondencias y resuelva.
Tambien se acepta un marcador cuadrado mediante `markerImageCorners`,
`markerSizeMeters` y `markerWorldPosition`.

La salida se guarda en:

```text
data/calibration/<camera_id>/intrinsics.json
data/calibration/<camera_id>/world.json
```

Valide con una distancia/punto conocido adicional usando
`POST /api/calibration/validate`. Si la camara se mueve o cambia la optica,
establezca `CALIBRATION_INVALIDATED=1`, detenga el escaneo y calibre otra vez.
La aplicacion detecta cambios de
resolucion y errores de reproyeccion/validacion; sin un marcador permanente no
puede detectar automaticamente todos los movimientos fisicos.

## Escanear y corregir la escena

1. Deje el lugar vacio o con el menor transito posible.
2. Verifique en `/configuration` que intrinsecos, mundo, resolucion y profundidad
   (cuando corresponda) sean validos.
3. Pulse **Iniciar**. Se capturan entre 30 y 100 frames segun `SCAN_FRAME_COUNT`.
4. Solo se proponen objetos estables que superen tasa de deteccion y tolerancias.
5. Revise las propuestas. El modelo YOLO de personas **no** se reutiliza para
   inventar mesas, racks o paredes.
6. Configure `SCENE_MODEL_PATH` con un modelo de segmentacion del local y
   `SCENE_CLASS_MAP`, o dibuje manualmente el contacto/huella del objeto.
7. Introduzca manualmente altura si el modo monocular no puede observarla.
8. Mueva vertices arrastrando los puntos naranjas y elimine falsos positivos.

Las clases permitidas son `wall`, `table`, `shelf`, `rack`, `display`,
`checkout`, `bench`, `column` y `other`. Las areas operativas se dibujan en la
vista principal y se mantienen separadas de los obstaculos fisicos.

La escena aprobada se versiona en `data/scenes/<camera_id>/scene.json`. Conserva
poligonos compactos y una matriz fija dentro del campo de vision calibrado. La
matriz se limita a 100 000 puntos para evitar configuraciones accidentales que
agoten memoria.

## API Flask

Se conservan `/video_feed`, `/stats` y `/add_area`. Los endpoints nuevos son:

```text
GET  /api/calibration/status
POST /api/calibration/intrinsics/capture
POST /api/calibration/intrinsics/solve
POST /api/calibration/world/solve
POST /api/calibration/validate
POST /api/scene/scan/start
GET  /api/scene/scan/status
POST /api/scene/scan/stop
GET  /api/scene
PUT  /api/scene
POST /api/scene/objects
PATCH /api/scene/objects/<object_id>
DELETE /api/scene/objects/<object_id>
GET  /api/live/tracks
GET  /api/live/frame
GET  /api/stream
GET  /api/coordinates/image-to-ground?u=<px>&v=<px>
GET  /api/v1/sites
GET  /api/v1/sites/<site_id>/bootstrap
GET  /api/v1/sites/<site_id>/track-points
GET  /api/v1/sites/<site_id>/area-state
```

Los cuatro endpoints `/api/v1/sites` forman la API local de la presentacion y
usan exactamente los nombres del contrato de `mrMain371/visioflow`. El servidor
definitivo debe reemplazar el buffer en memoria de `app/demo_api.py` por la
persistencia PostgreSQL definida en el repositorio frontend.

Las mutaciones requieren una sesion Flask administradora. Los GET requieren
sesion autenticada. `/api/live/tracks` comparte las versiones de calibracion y
escena. Si falta profundidad/calibracion, `x`, `y` y `z` son `null` y
`positionValid` es falso; nunca se completa un valor ficticio.

Ejemplo valido:

```json
{
  "cameraId": "cam-01",
  "frameId": 158420,
  "capturedAt": "2026-08-02T18:00:00.000Z",
  "coordinateSystem": {
    "name": "world_ground",
    "unit": "meter",
    "origin": "camera_floor_projection",
    "xAxis": "right",
    "yAxis": "forward",
    "zAxis": "up"
  },
  "calibrationVersion": 1,
  "sceneVersion": 1,
  "tracks": [
    {
      "trackerId": "trk-184",
      "imagePoint": {"u": 824, "v": 591, "coordinateSystem": {"name": "image", "unit": "pixel"}},
      "worldPoint": {"x": 2.31, "y": 4.72, "z": 0, "depthMethod": "ground_plane", "approximate": true},
      "x": 2.31,
      "y": 4.72,
      "z": 0,
      "confidence": 0.93,
      "positionValid": true
    }
  ]
}
```

## Pruebas

Las pruebas usan matrices sinteticas, fixtures y la fabrica Flask con el hilo de
camara desactivado; no requieren hardware:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Limitaciones conocidas

- La precision depende de mediciones, cobertura ChArUco, pose y calidad del
  sensor. La UI muestra sus errores, metodo y version.
- Una sola camara RGB no puede medir altura ni profundidad general.
- Muros, aparadores y racks requieren segmentacion entrenada o correccion manual.
- Oclusiones del contacto con el suelo requieren correccion manual.
- El adaptador RGB-D concreto depende del SDK/hardware elegido; el proveedor base
  ya valida mapas alineados en metros y bloquea el escaneo si faltan.
