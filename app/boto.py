import boto3
from botocore.client import Config
from app.config import settings

session = boto3.session.Session(
    aws_access_key_id=settings.MINIO_ACCESS_KEY,
    aws_secret_access_key=settings.MINIO_SECRET_KEY,
    region_name='us-east-1'
)

client = session.client(
    's3', 
    endpoint_url=settings.MINIO_ENDPOINT,
    config=Config(signature_version='s3v4')
)

def check_and_create_bucket(bucket_name: str):
    try:
        client.head_bucket(Bucket=bucket_name)
    except Exception:
        try:
            client.create_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' created successfully.")
        except Exception as e:
            print(f"Error creating bucket: {e}")
            raise e

def upload_file_obj(file_obj, bucket_name: str, object_name: str, content_type: str):
    try:
        check_and_create_bucket(bucket_name)
        
        client.upload_fileobj(
            file_obj,
            bucket_name,
            object_name,
            ExtraArgs={"ContentType": content_type}
        )
        print(f"File '{object_name}' uploaded successfully to bucket '{bucket_name}'.")
        return object_name
    except Exception as e:
        print(f"Error uploading file object: {e}")
        raise e

def generate_presigned_download_url(bucket_name: str, object_name: str, expires_in: int = 3600):
    try:
        url = client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expires_in
        )
        return url
    except Exception as e:
        print(f"Error generating presigned URL: {e}")
        raise e