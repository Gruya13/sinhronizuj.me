# Koristimo zvanicni PyTorch Docker image sa podrskom za CUDA 11.8 i cuDNN.
# Ovo je najoptimalnija baza za RunPod i graficke kartice (NVIDIA) jer u startu sadrzi vecinu teskih AI drajvera.
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

# Postavljamo varijable okruzenja da bi se zaobisla razna interaktivna pitanja instalacija
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Kreiramo i idemo u glavni radni folder
WORKDIR /app

# Instalacija sistemskih zavisnosti koje su kriticne za obradu videa i OpenCV
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    libgl1 \
    libglib2.0-0 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Kopiramo listu Python biblioteka i instaliramo ih
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiramo ostatak izvornog koda iz repozitorijuma
COPY . .

# Kreiramo folder za izlazne fajlove
RUN mkdir -p /app/temp_workspace
