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

def delete_file(bucket_name: str, object_name: str):
    """Delete a file from the specified bucket."""
    try:
        client.delete_object(Bucket=bucket_name, Key=object_name)
        print(f"File '{object_name}' deleted successfully from bucket '{bucket_name}'.")
    except Exception as e:
        print(f"Error deleting file '{object_name}' from bucket '{bucket_name}': {e}")
        raise e

def generate_presigned_upload_post(bucket_name: str, object_name: str, content_type: str, max_size_mb: int = 10):
    """Generate a presigned POST policy and signature for direct client-side upload."""
    try:
        check_and_create_bucket(bucket_name)
        max_size_bytes = max_size_mb * 1024 * 1024
        
        response = client.generate_presigned_post(
            Bucket=bucket_name,
            Key=object_name,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 0, max_size_bytes]
            ],
            ExpiresIn=600  # 10 minutes
        )
        return response
    except Exception as e:
        print(f"Error generating presigned post: {e}")
        raise e