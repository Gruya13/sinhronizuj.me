#!/bin/bash
set -e

# Učitavanje .env fajla
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

DB_USER=${POSTGRES_USER:-sinhronizuj_user}
DB_NAME=${POSTGRES_DB:-sinhronizuj_db}

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    # Ako fajl nije prosleđen, uzimamo najnoviji iz backups foldera
    BACKUP_FILE=$(ls -t backups/backup_*.tar.gz 2>/dev/null | head -n 1)
fi

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "[RESTORE ERROR] Backup fajl nije pronađen. Navedite putanju do arhive: ./scripts/restore.sh <putanja_do_arhive>"
    exit 1
fi

echo "[RESTORE] Koristim backup arhivu: $BACKUP_FILE"

# Otpakujemo arhivu
echo "[RESTORE] Raspakujem arhivu..."
tar -xzf "$BACKUP_FILE"

# Obnavljamo bazu podataka
echo "[RESTORE] Obnavljam bazu podataka..."
if docker compose ps | grep -q "db"; then
    # Prvo brišemo i kreiramo bazu kako bi oporavak bio čist
    docker compose exec -T db dropdb -U "$DB_USER" --if-exists "$DB_NAME"
    docker compose exec -T db createdb -U "$DB_USER" "$DB_NAME"
    # Uvozimo dump
    docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" < backups/db_backup.sql
else
    echo "[WARNING] Kontejner 'db' nije pokrenut. Pokušavam lokalni pg_restore/psql..."
    PGPASSWORD=${DB_PASSWORD:-sinhronizuj_pass_2026} dropdb -h localhost -p 5435 -U "$DB_USER" --if-exists "$DB_NAME"
    PGPASSWORD=${DB_PASSWORD:-sinhronizuj_pass_2026} createdb -h localhost -p 5435 -U "$DB_USER" "$DB_NAME"
    PGPASSWORD=${DB_PASSWORD:-sinhronizuj_pass_2026} psql -h localhost -p 5435 -U "$DB_USER" -d "$DB_NAME" < backups/db_backup.sql
fi

echo "[RESTORE] Baza podataka uspešno obnovljena."

# Pozivamo Python skriptu za oporavak S3
echo "[RESTORE] Pokrećem oporavak S3 skladišta..."
./venv/bin/python scripts/restore_s3.py

echo "[RESTORE FINISHED] Oporavak sistema je uspešno završen!"
