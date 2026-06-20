import os
import tarfile
import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "sinhronizuj_minio_key")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "sinhronizuj_minio_secret")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "sinhronizuj-me")

def backup_s3():
    s3 = boto3.client(
        's3',
        endpoint_url=f"http://{MINIO_ENDPOINT}" if not settings_secure() else f"https://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    tar_path = os.path.join(backup_dir, "s3_backup.tar.gz")
    
    print(f"[BACKUP] Započinjem bekap S3 bucketa '{MINIO_BUCKET}' u {tar_path}...")
    
    try:
        temp_dir = "temp_s3_backup"
        os.makedirs(temp_dir, exist_ok=True)
        
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=MINIO_BUCKET)
        
        count = 0
        with tarfile.open(tar_path, "w:gz") as tar:
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        # Izbegavamo keš i privremene fajlove
                        if key.startswith("cache/"):
                            continue
                        local_file = os.path.join(temp_dir, key)
                        os.makedirs(os.path.dirname(local_file), exist_ok=True)
                        
                        s3.download_file(MINIO_BUCKET, key, local_file)
                        tar.add(local_file, arcname=key)
                        os.remove(local_file)
                        count += 1
                        print(f"Dodato u backup: {key}")
                        
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)
            
        print(f"[BACKUP] Uspešno bekapovano {count} objekata sa S3.")
    except Exception as e:
        print(f"[BACKUP ERROR] Greška pri bekapu S3: {e}")

def settings_secure():
    return MINIO_SECURE

if __name__ == "__main__":
    backup_s3()
