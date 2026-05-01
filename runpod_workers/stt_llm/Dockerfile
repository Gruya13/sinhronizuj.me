# ==========================================
# 1. BUILDER STAGE
# ==========================================
FROM python:3.10-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-stt-llm.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir https://github.com/Dao-AILab/flash-attention/releases/download/v2.6.3/flash_attn-2.6.3+cu121torch2.4cxx11abiFALSE-cp310-cp310-linux_x86_64.whl && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements-stt-llm.txt

# ==========================================
# 2. FINAL RUNTIME STAGE
# ==========================================
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY handler.py .

CMD ["python", "-u", "handler.py"]
