FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements-tts.txt .

RUN pip install --no-cache-dir -r requirements-tts.txt

# Pre-compiled flash-attn wheel za brzo instaliranje bez build timeout-a
RUN pip install --no-cache-dir https://github.com/Dao-AILab/flash-attention/releases/download/v2.6.3/flash_attn-2.6.3+cu121torch2.4cxx11abiFALSE-cp310-cp310-linux_x86_64.whl

COPY handler.py .

CMD ["python", "-u", "handler.py"]
