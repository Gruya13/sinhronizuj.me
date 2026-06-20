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
