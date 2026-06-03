#!/usr/bin/env python
import os
import sys
import subprocess
import datetime
import boto3
from botocore.config import Config

# Add project root to python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_root)

from backend.core.config import settings

def run_backup():
    print(f"[{datetime.datetime.now()}] Započinjem backup proces baze podataka...")
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.sql.gz"
    backup_local_path = os.path.join("/tmp", backup_filename)
    
    db_user = "sinhronizuj_user"
    db_name = "sinhronizuj_db"
    db_pass = os.getenv("DB_PASSWORD", "sinhronizuj_pass_2026")
    
    # 1. Pokrećemo pg_dump u docker kontejneru i gzipujemo rezultat
    cmd = f"docker exec -e PGPASSWORD={db_pass} sinhronizuj-db pg_dump -U {db_user} -d {db_name} | gzip > {backup_local_path}"
    
    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"Database dump uspešno kreiran na lokaciji: {backup_local_path}")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] pg_dump komanda nije uspela: {e}")
        sys.exit(1)
        
    # 2. Otpremamo backup fajl na MinIO (S3) bucket pod nazivom 'backups'
    bucket_name = "backups"
    
    s3_client = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    try:
        # Proveravamo i kreiramo backups bucket ako ne postoji
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except Exception:
            print(f"Bucket '{bucket_name}' ne postoji. Kreiram ga...")
            s3_client.create_bucket(Bucket=bucket_name)
            
        print(f"Otpremam {backup_filename} na MinIO u bucket '{bucket_name}'...")
        s3_client.upload_file(backup_local_path, bucket_name, backup_filename)
        print("Otpremanje uspešno završeno.")
    except Exception as e:
        print(f"[ERROR] S3 upload backup-a nije uspeo: {e}")
        if os.path.exists(backup_local_path):
            os.remove(backup_local_path)
        sys.exit(1)
        
    # 3. Uklanjamo lokalni backup fajl
    if os.path.exists(backup_local_path):
        os.remove(backup_local_path)
        
    # 4. Rotacija: Brišemo bekapa starije od 7 dana na S3
    try:
        print("Pokrećem rotaciju backup-a na S3 (zadržavamo poslednjih 7 dana)...")
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            threshold = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
            for obj in response['Contents']:
                last_modified = obj['LastModified']
                if last_modified < threshold:
                    print(f"Brišem stari backup sa S3: {obj['Key']} (modifikovan: {last_modified})")
                    s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])
        print("Rotacija uspešno završena.")
    except Exception as e:
        print(f"[WARNING] Rotacija starih backup-a na S3 nije uspela: {e}")
        
    print(f"[{datetime.datetime.now()}] Backup proces je uspešno kompletiran!")

if __name__ == "__main__":
    run_backup()
