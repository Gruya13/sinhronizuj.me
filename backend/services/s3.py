import boto3
from botocore.config import Config
from backend.core.config import settings

def get_presigned_download_url(bucket_name: str, object_key: str, expires_in: int = 300) -> str:
    if not object_key:
        return ""
    if object_key.startswith("http://") or object_key.startswith("https://"):
        return object_key
        
    s3_public = boto3.client(
        's3',
        endpoint_url=settings.MINIO_PUBLIC_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    try:
        url = s3_public.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expires_in
        )
        return url
    except Exception as e:
        print(f"[ERROR] Greška pri generisanju pre-signed URL-a za preuzimanje: {e}", flush=True)
        return ""

def get_presigned_upload_url(bucket_name: str, object_key: str, expires_in: int = 300) -> str:
    if not object_key:
        return ""
        
    s3_public = boto3.client(
        's3',
        endpoint_url=settings.MINIO_PUBLIC_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    try:
        url = s3_public.generate_presigned_url(
            ClientMethod='put_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_key,
                'ContentType': 'video/mp4'
            },
            ExpiresIn=expires_in
        )
        return url
    except Exception as e:
        print(f"[ERROR] Greška pri generisanju pre-signed URL-a za otpremanje: {e}", flush=True)
        return ""

def upload_file_to_s3(file_path: str, bucket_name: str, object_key: str) -> bool:
    import os
    if not os.path.exists(file_path):
        print(f"[S3 UPLOAD ERROR] Lokalni fajl ne postoji: {file_path}", flush=True)
        return False
    s3_internal = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name=settings.S3_REGION
    )
    try:
        s3_internal.upload_file(file_path, bucket_name, object_key)
        print(f"[S3 UPLOAD SUCCESS] Otpremljen {file_path} -> s3://{bucket_name}/{object_key}", flush=True)
        return True
    except Exception as e:
        print(f"[S3 UPLOAD ERROR] Greška pri otpremanju na S3: {e}", flush=True)
        return False

def download_file_from_s3(bucket_name: str, object_key: str, local_path: str) -> bool:
    s3_internal = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name=settings.S3_REGION
    )
    try:
        s3_internal.download_file(bucket_name, object_key, local_path)
        print(f"[S3 DOWNLOAD SUCCESS] Preuzet s3://{bucket_name}/{object_key} -> {local_path}", flush=True)
        return True
    except Exception as e:
        print(f"[S3 DOWNLOAD ERROR] Greška pri preuzimanju sa S3: {e}", flush=True)
        return False

def delete_file_from_s3(bucket_name: str, object_key: str) -> bool:
    s3_internal = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name=settings.S3_REGION
    )
    try:
        s3_internal.delete_object(Bucket=bucket_name, Key=object_key)
        print(f"[S3 DELETE SUCCESS] Obrisan s3://{bucket_name}/{object_key}", flush=True)
        return True
    except Exception as e:
        print(f"[S3 DELETE ERROR] Greška pri brisanju sa S3: {e}", flush=True)
        return False



