# Visio Flow - contador Flask (OpenCV, YOLOv8, DeepSort). Habla con FastAPI por HTTP, no con PostgreSQL.
FROM python:3.11-slim

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

COPY . .

EXPOSE 5000

CMD ["python", "run.py"]
