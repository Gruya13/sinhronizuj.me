FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-stt-llm.txt .

# 1. Prvo instaliramo PyTorch (kako bi flash-attn imao osnovu za instalaciju)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.4.0 torchaudio==2.4.0 --extra-index-url https://download.pytorch.org/whl/cu121

# 2. Zatim instaliramo pre-compiled flash-attn wheel (zaobilazimo 40min build)
RUN pip install --no-cache-dir https://github.com/Dao-AILab/flash-attention/releases/download/v2.6.3/flash_attn-2.6.3+cu121torch2.4cxx11abiFALSE-cp310-cp310-linux_x86_64.whl

# 3. Na kraju instaliramo vLLM i Faster-Whisper. Pip će videti da je flash-attn već tu i preskočiće build sa izvornog koda!
RUN pip install --no-cache-dir -r requirements-stt-llm.txt

COPY handler.py .

CMD ["python", "-u", "handler.py"]
