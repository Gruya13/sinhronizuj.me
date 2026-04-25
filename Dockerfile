# Laksa baza bez CUDA drajvera (Hetzner Control Plane je CPU-only)
FROM python:3.11-slim

# Spoljne zavisnosti
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Instalacija sistemskih alata (FFmpeg je neophodan za Demucs i Merger)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalacija Python paketa
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiranje koda
COPY . .

RUN mkdir -p /app/temp_workspace

# API port
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
