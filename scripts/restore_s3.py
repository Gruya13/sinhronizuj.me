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

def restore_s3():
    s3 = boto3.client(
        's3',
        endpoint_url=f"http://{MINIO_ENDPOINT}" if not settings_secure() else f"https://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    tar_path = "backups/s3_backup.tar.gz"
    if not os.path.exists(tar_path):
        print(f"[RESTORE ERROR] Backup fajl ne postoji: {tar_path}")
        return
        
    print(f"[RESTORE] Oporavljam S3 bucket '{MINIO_BUCKET}' iz {tar_path}...")
    
    try:
        s3.head_bucket(Bucket=MINIO_BUCKET)
    except Exception:
        try:
            s3.create_bucket(Bucket=MINIO_BUCKET)
            print(f"Kreiran bucket: {MINIO_BUCKET}")
        except Exception as e:
            print(f"[RESTORE WARNING] Nije moguće kreirati bucket (možda već postoji): {e}")
        
    try:
        temp_dir = "temp_s3_restore"
        os.makedirs(temp_dir, exist_ok=True)
        
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=temp_dir)
            
            count = 0
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    local_path = os.path.join(root, file)
                    rel_path = os.path.relpath(local_path, temp_dir)
                    
                    s3.upload_file(local_path, MINIO_BUCKET, rel_path)
                    count += 1
                    print(f"Oporavljeno na S3: {rel_path}")
                    
        import shutil
        shutil.rmtree(temp_dir)
        print(f"[RESTORE] Uspešno oporavljeno {count} objekata na S3.")
    except Exception as e:
        print(f"[RESTORE ERROR] Greška pri oporavku S3: {e}")

def settings_secure():
    return MINIO_SECURE

if __name__ == "__main__":
    restore_s3()
