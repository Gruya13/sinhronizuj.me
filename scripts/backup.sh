#!/bin/bash
set -e

# Učitavanje .env fajla
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

DB_USER=${POSTGRES_USER:-sinhronizuj_user}
DB_NAME=${POSTGRES_DB:-sinhronizuj_db}

echo "[BACKUP] Započinjem bekap PostgreSQL baze..."
mkdir -p backups

# Bekap baze iz kontejnera db
if docker compose ps | grep -q "db"; then
    docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > backups/db_backup.sql
else
    echo "[WARNING] Kontejner 'db' nije pokrenut. Pokušavam sa lokalnim pg_dump..."
    PGPASSWORD=${DB_PASSWORD:-sinhronizuj_pass_2026} pg_dump -h localhost -p 5435 -U "$DB_USER" -d "$DB_NAME" > backups/db_backup.sql
fi

echo "[BACKUP] Baza uspešno bekapovana u backups/db_backup.sql"

# Pozivamo Python skriptu za bekap S3
echo "[BACKUP] Pokrećem bekap S3 skladišta..."
./venv/bin/python scripts/backup_s3.py

# Pravimo finalnu arhivu sa timestamp-om
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
tar -czf "backups/backup_$TIMESTAMP.tar.gz" backups/db_backup.sql backups/s3_backup.tar.gz

echo "[BACKUP FINISHED] Bekap je uspešno završen: backups/backup_$TIMESTAMP.tar.gz"
