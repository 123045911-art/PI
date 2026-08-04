# Visio Flow - contador Flask (OpenCV, YOLOv8, DeepSort). Habla con FastAPI por HTTP, no con PostgreSQL.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000

WORKDIR /app

# Librerías de sistema usadas por OpenCV / ultralytics / video
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Ultralytics declara opencv-python. Reinstalar la variante contrib garantiza
# cv2.aruco/ChArUco y evita mezclar dos distribuciones que escriben el mismo cv2.
RUN pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python || true && \
    pip install --no-cache-dir "opencv-contrib-python-headless>=4.8,<5"

COPY . .

EXPOSE 5000

CMD ["python", "run.py"]
