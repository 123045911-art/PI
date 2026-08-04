# Datos dinámicos y textos de VisioFlow

Este documento distingue datos reales, textos calculados y etiquetas fijas de interfaz.

## Áreas y cámaras

- `GET /api/v1/sites` devuelve las fuentes disponibles.
- `GET /api/v1/sites/{siteId}/bootstrap` devuelve cámaras, áreas, escena y objetos.
- El frontend actualiza la lista de cámaras cada 5 segundos y el `bootstrap` de la cámara activa cada 2 segundos.
- Las áreas creadas en Flask se guardan en `data/areas/{cameraId}.json`; sobreviven al reinicio.
- Crear, editar o eliminar un área cambia el siguiente `bootstrap`. El mapa y el creador de alertas se recalculan aunque no haya personas detectadas.

Los nombres mostrados no están concatenados en el frontend: vienen de `camera.name` y `area.name`.

## Alertas

Una regla de alta afluencia guarda:

```json
{
  "areaId": "zona-cercana",
  "areaName": "Zona cercana",
  "type": "crowding",
  "thresholdPeople": 12,
  "reason": "Avisar cuando haya 12 personas o más.",
  "peopleCountSnapshot": 7,
  "status": "watching"
}
```

La frase se genera con el tipo y el umbral seleccionados:

- `crowding`: `Avisar cuando haya {thresholdPeople} personas o más.`
- `low_flow`: `Avisar cuando haya {thresholdPeople} personas o menos.`

No se inventan nombres de áreas ni conteos. `areaName` viene del área seleccionada, el umbral lo elige el usuario y `peopleCountSnapshot` viene del último cálculo.

El estado también es dinámico:

- Alta afluencia se cumple cuando `peopleCount >= thresholdPeople`.
- Baja afluencia se cumple cuando `peopleCount <= thresholdPeople`.
- La programación decide si la regla se evalúa ese día.
- Cuando cambia el conteo, se recalculan `status` y `peopleCountSnapshot`.

Al editar una regla se vuelve a generar su descripción con los valores nuevos. Al eliminarla se guarda una marca de eliminación para que no reaparezca después de reiniciar.

## Texto fijo permitido

Son etiquetas de navegación, no afirmaciones sobre datos:

- `Cámaras disponibles`
- `Alta afluencia`
- `Baja afluencia`
- `En espera`
- `Condición cumplida`
- `Eliminar`

## Contenido retirado

- Reportes manuales del frontend.
- Historial ficticio de alertas con frases como “el conteo alcanzó el umbral durante el cierre”.
- Mensajes internos sobre conexión pendiente, JWT o trabajo futuro.

Las alertas que se muestran ahora son las creadas por el usuario y evaluadas contra los conteos disponibles.
