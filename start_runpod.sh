#!/bin/bash
echo "=== Pokretanje instalacije Daca Dub sistema na RunPod-u ==="

# Instalacija neophodnih sistemskih paketa (Redis je kljucan za Celery)
apt-get update
apt-get install -y redis-server tmux ffmpeg libgl1

# Pokretanje Redis servera u pozadini
service redis-server start

# Instalacija Python zavisnosti
pip install --no-cache-dir -r requirements.txt

# Postavljanje Python putanje
export PYTHONPATH=/workspace/daca_dub

echo "Sve je instalirano! Sistem se podize u TMUX sesijama..."

# Pokretanje API servera u prvoj tmux sesiji
tmux new-session -d -s api "uvicorn backend.main:app --host 0.0.0.0 --port 8000"

# Pokretanje Celery radnika u drugoj tmux sesiji
tmux new-session -d -s worker "celery -A backend.worker.celery_app worker --loglevel=info --concurrency=1"

echo "=== DACA DUB JE SPREMAN! ==="
echo "API slusa na portu 8000."
echo "Da pogledas logove radnika (kako se skida i obradjuje video), kucaj:"
echo "tmux attach -t worker"
