# Sistema de Visión Computarizada y Dashboard (PI)

Este proyecto se divide en los siguientes módulos:
1. **Contador de Personas (Python / Flask):** Un script de visión computarizada que utiliza YOLOv8 y DeepSORT para detectar personas, rastrearlas y registrar su entrada/salida en diferentes áreas. Se gestiona desde una página web desarrollada en Flask..
2. **Dashboard de Análisis (Laravel):** Una aplicación web para visualizar los datos generados por el script de Python.
3. **API (FastAPI):** Aplicación de FastAPI para gestionar información mediante endpoints y una estructura de carpetas que divide el proyecto en secciones:
- Modelos
- Datos
- Rutas
- Seguridad
4. **Base de datos (PostgreSQL):** Sistema de gestión de base de datos para almacenamiento y administración de información manejada por el proyecto.

---

## 1. Configuración de Docker

El proyecto funciona mediante el uso de contenedores de Docker. Es necesaria la instalación de **Docker Desktop** para la correcta construcción y levantamiento de todos los módulos del sistema. Esto asegura una ejecución segura de todos los servicios para un correcto funcionamiento del proyecto.

## 2. Contador de Personas (Python)

Ubicación: `contador_personas/`

### Requisitos previos
- **Python 3.8+** instalado.
- **Cámara web** o cámara IP accesible.
- Base de datos **MySQL** si se desea guardar los logs remotamente.

### Instalación de dependencias

Es altamente recomendable usar un entorno virtual:
```bash
cd contador_personas
python -m venv venv

# Activar el entorno virtual:
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
```

Instala las librerías necesarias ejecutando:
```bash
pip install opencv-python numpy ultralytics deep-sort-realtime customtkinter pillow mysql-connector-python
```

### Uso

Para ejecutar el programa con la cámara predeterminada y su configuración de base de datos leída desde el entorno:
```bash
python PI.py
```

**Argumentos opcionales (por terminal):**
- `--source <indice o url>`: Para especificar qué cámara usar (ej. `--source 1` o `--source http://IP/video`).
- `--list-cams`: Muestra una lista de las cámaras disponibles por índice.
- `--db-disable`: Ejecuta el script sin intentar conectarse a la base de datos MySQL.
- `--db-heatmap`: Activa el registro de puntos de calor (heatmap).
- `--db-host`, `--db-user`, `--db-pass`, `--db-name`: Para sobreescribir las credenciales locales de la base de datos.

---

## 3. Dashboard de Análisis (Laravel)

Ubicación: `contador_dashboard/`

### Requisitos previos
- **PHP 8.2** o superior.
- **Composer** instalado.
- **Node.js** y **NPM**.
- Base de datos compatible (MySQL, SQLite, etc.)

### Instalación y Configuración

1. **Instalar dependencias de PHP:**
   ```bash
   cd contador_dashboard
   composer install
   ```

2. **Instalar dependencias de Node (Frontend):**
   ```bash
   npm install
   npm run build
   # (Usa npm run dev si estás desarrollando)
   ```

3. **Configurar el entorno:**
   Copia el archivo de ejemplo para crear tu propio `.env`:
   ```bash
   cp .env.example .env
   ```
   *Abre el archivo `.env` y configura tu conexión a la Base de Datos (DB_CONNECTION, DB_HOST, DB_DATABASE, etc.) para que coincida con la que usa tu script de Python.*

4. **Generar la llave de la aplicación y correr migraciones:**
   ```bash
   php artisan key:generate
   php artisan migrate
   ```

### Ejecución

Para iniciar el servidor de desarrollo local de Laravel:
```bash
php artisan serve
```
Y visita `http://127.0.0.1:8000` en tu navegador.

---

## Flujo de Funcionamiento
1. Enciende y configura tu entorno de Base de Datos.
2. Inicia el Dashboard con `php artisan serve` para monitoreo web.
3. Ejecuta `python PI.py` para abrir la interfaz de visión. 
4. En la interfaz de Python, dibuja las áreas que deseas monitorear. Las estadísticas de entrada/salida se guardarán automáticamente en la base de datos y se reflejarán en el Dashboard.
