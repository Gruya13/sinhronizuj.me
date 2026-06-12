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
        
    # 2. Otpremamo backup fajl na S3 (podržava i eksterni i lokalni MinIO)
    backup_endpoint = os.getenv("BACKUP_S3_ENDPOINT")
    backup_access_key = os.getenv("BACKUP_S3_ACCESS_KEY")
    backup_secret_key = os.getenv("BACKUP_S3_SECRET_KEY")
    backup_bucket = os.getenv("BACKUP_S3_BUCKET", "backups")
    backup_secure = os.getenv("BACKUP_S3_SECURE", "True").lower() == "true"
    
    if backup_endpoint and backup_access_key and backup_secret_key:
        endpoint_url = f"https://{backup_endpoint}" if backup_secure else f"http://{backup_endpoint}"
        aws_access_key_id = backup_access_key
        aws_secret_access_key = backup_secret_key
        bucket_name = backup_bucket
        print(f"Koristim EKSTERNI S3 backup endpoint: {endpoint_url} (bucket: {bucket_name})")
    else:
        endpoint_url = f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}"
        aws_access_key_id = settings.MINIO_ACCESS_KEY
        aws_secret_access_key = settings.MINIO_SECRET_KEY
        bucket_name = "backups"
        print(f"Upozorenje: Nisu definisani eksterni S3 akreditivi. Koristim lokalni MinIO: {endpoint_url}")
        
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
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
