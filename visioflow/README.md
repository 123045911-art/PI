# VisioFlow

Aplicación móvil responsiva en React Native + Expo para representar trayectorias de personas como superficies térmicas 2.5D y patrones operativos verificables.

La prueba integral del pasillo real, sus tres áreas, selección de sitio y API local está documentada en [`docs/prueba-integral-pasillo.md`](docs/prueba-integral-pasillo.md).

Para la presentación completa, ejecuta `iniciar-presentacion-completa.bat`. El script detecta la IP LAN, inicia Flask con la Dell WB7022, espera la API y después abre Expo Go con la URL correcta. `detener-presentacion.bat` cierra únicamente los servicios que escuchan en los puertos 5000 y 8081.

## Ejecutar con Expo Go

Puedes abrir `iniciar-visioflow.bat` y elegir LAN o túnel. También puedes ejecutar:

```powershell
cd C:\Users\luisi\Desktop\visioflow
npx expo start --lan --go
```

Usa Node.js 22.13+ o 24.3+ para coincidir con los requisitos de Metro.

## Datos utilizados

Los mapas y análisis de VisioFlow usan exclusivamente las observaciones disponibles en `init.sql`:

- `track_id`: identificador temporal de la persona detectada.
- `timestamp`: momento de la observación.
- `cx`, `cy`: coordenadas de la persona.
- `area_id`: área asociada cuando existe.
- `area_events`: entradas, salidas y permanencia.
- `area_state`: conteo actual por área.
- `areas`: rectángulos semánticos del espacio.

`database/schema.sql` agrega `static_objects` para representar la segunda matriz sin temporalidad: muros, islas físicas, aparadores y módulos. También deja preparados `users` y `alerts` para el backend futuro.

La app no calcula compras, conversión, identidad, ingresos o capacidad, porque esos datos no forman parte del contrato disponible.

## Métricas

- **Personas:** identificadores diferentes que recorrieron cada sector espacial.
- **Tiempo en zona:** segundos derivados de muestras consecutivas de una persona dentro de un área.
- **Densidad:** personas simultáneas promedio en intervalos de 20 segundos.
- **Concurrencia pico:** máximo de personas simultáneas observado.
- **Transiciones:** cambios consecutivos entre áreas por track.

## Visualización

- Superficie KDE 2.5D con gradiente blanco, amarillo, naranja y rojo, altura proporcional a la métrica, ondulación temporal y curvas de nivel.
- Escena de demostración limitada al campo de visión parcial de una cámara en una tienda de ropa; no representa la planta completa.
- Estructuras fijas extruidas y usadas como obstáculos: el calor y los recorridos las rodean aun cuando la capa visual está oculta.
- Áreas operativas independientes y seleccionables.
- Personas activas y recorridos recientes como capas opcionales.
- Vistas isométrica y superior.
- Ventana móvil, acumulado hasta el momento y promedio general.

## Análisis

Los textos no contienen porcentajes fijos. Se construyen a partir del periodo visible usando:

- Área con mayor cantidad de personas diferentes.
- Área con mayor permanencia mediana.
- Transición más frecuente entre áreas.
- Distribución temporal en intervalos de una hora.

Cada tarjeta muestra el valor que sustenta el patrón y permite seleccionar el área correspondiente.

La demostración también incluye 2,688 agregados zona–hora derivados de 56 días simulados. La hoja móvil de **Análisis** se abre deslizando hacia arriba y permite:

- Ver la zona interior con mayor afluencia para cada hora o para rangos de dos horas.
- Filtrar el promedio por día de la semana.
- Comparar las dos semanas recientes contra las seis anteriores.
- Detectar descensos, crecimiento semanal y patrones zona–día estables.
- Abrir un modal de trabajo con pestañas separadas para comparar, revisar horarios y estudiar patrones.
- Contrastar dos horas mediante un mapa divergente normalizado por cada 100 recorridos: azul representa menor presencia relativa y naranja mayor presencia relativa.

La reproducción empieza pausada. Elegir un día, seleccionar un área o abrir **Análisis** también detiene la animación para que los valores puedan leerse y compararse sin cambiar cada fracción de segundo. El selector **Día del mapa** aplica el mismo día al mapa, los indicadores, la comparación horaria y el panel de análisis.

Al tocar un área del mapa se abre una ficha específica con:

- afluencia de la jornada seleccionada;
- personas registradas en cada hora y acumulado progresivo;
- hora pico;
- cambio frente al día anterior.

En la simulación, el acumulado diario suma las personas distintas observadas dentro de cada hora. Cuando exista el backend, el identificador temporal permitirá añadir un total diario deduplicado sin cambiar la interfaz.

Los KPI superiores tienen tres alcances explícitos: **Generales** (estables para toda la jornada), **En vivo** (actualización temporal) y **Periodo seleccionado** (se congela al seleccionar una comparación).

El acceso se excluye únicamente del ranking horario de zonas interiores porque aparece en casi todas las rutas; sigue incluido en el mapa y en las métricas generales.

## Contrato de integración con visión y backend

`TRACK_POINTS` sigue siendo un conjunto determinístico de demostración: 900 personas a lo largo de una jornada de ocho horas, con distintas rutas, permanencias y tres olas de afluencia. El siguiente paso es reemplazarlo por un adaptador HTTP o de tiempo real que consulte un backend conectado a PostgreSQL. El frontend no debe conectarse directamente a la base de datos.

El contrato v1 listo para que el equipo construya el servidor está en un solo
documento: [`docs/server-specification.md`](docs/server-specification.md). Incluye
datos, tipos, frecuencias, peticiones, alertas, calibración y diagramas. Sus
anexos ejecutables son `docs/openapi.yaml`, `database/schema.sql` y
`src/apiContract.ts`.

La guía de instalación, ejecución con webcam, impresión del tablero ChArUco,
capturas desde distintas posiciones, calibración métrica y funcionamiento
interno está en
[`docs/tutorial-ejecucion-calibracion.md`](docs/tutorial-ejecucion-calibracion.md).

La fuente canónica conserva UTC y coordenadas `world_ground` en metros. Los píxeles de imagen se almacenan por separado. Los IDs públicos de sitio, cámara y área son cadenas estables; un tracker queda identificado por la combinación cámara, sesión y tracker para evitar colisiones entre reinicios.

## Acceso y alertas de demostración

- Usuario: `operador`
- Contraseña: `visioflow`
- El inicio de sesión y las alertas se guardan temporalmente como JSON local mediante AsyncStorage.
- El formulario valida área, tipo y motivo y conserva una captura del conteo visible.
- Las reglas de afluencia permiten elegir **alta** o **baja afluencia** y definir de 1 a 120 personas con un control deslizante naranja. La app indica si el último registro cumple la condición o si la regla permanece en espera.
- Cada regla puede aplicarse todos los días, repetirse un día concreto de la semana o ejecutarse en una fecha `AAAA-MM-DD`. El dashboard separa condiciones cumplidas, reglas en espera y reportes manuales recientes.
- Mientras la app está abierta, cada nuevo conteo vuelve a evaluar las reglas programadas. **En espera** significa que el umbral todavía no se cumple; **Condición cumplida** indica que el último registro sí lo cumple. Al producirse ese cambio, el estado se persiste y aparece un aviso tipo toast durante cinco segundos; al tocarlo se abre el gestor de alertas.
- Las reglas se crean para un área específica. El centro de alertas permite filtrar por área y contiene un historial simulado de casos resueltos para demostrar la consulta antes de conectar la API.
- El **reporte manual** no supervisa un umbral: registra un hecho que una persona ya observó. Su campo de texto documenta qué ocurrió, dónde afecta y por qué requiere atención.

Este almacenamiento es deliberadamente provisional. `src/localStore.ts` y `database/schema.sql` contienen el aviso de seguridad: antes de producción las credenciales deben salir del cliente, las contraseñas deben almacenarse en el backend como hash Argon2id con salt y la sesión debe usar tokens seguros. API, dos servidores, balanceador de carga, firewall, SSL, JWT y monitoreo siguen siendo responsabilidades del backend y la infraestructura futura; la app no los declara como implementados.
