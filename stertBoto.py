import os
import io
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from app.config import settings

# ==========================================
# 1. ESTABLISH THE CONNECTIONS
# ==========================================
MINIO_ENDPOINT = settings.MINIO_ENDPOINT
ACCESS_KEY = settings.MINIO_ACCESS_KEY
SECRET_KEY = settings.MINIO_SECRET_KEY
BUCKET_NAME = "automated-pipeline-bucket"

# Configure standard path-style routing for local deployments
s3_config = Config(
    s3={'addressing_style': 'path'},
    signature_version='s3v4'
)

s3 = boto3.client(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=s3_config
)

def run_pipeline():
    print("🚀 Starting automated MinIO lifecycle script...\n")

    # ==========================================
    # 2. BUCKET MANAGEMENT & IDEMPOTENCY
    # ==========================================
    try:
        print(f"Checking if bucket '{BUCKET_NAME}' exists...")
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"✅ Bucket '{BUCKET_NAME}' already exists. Proceeding.")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"⚠️ Bucket missing. Creating '{BUCKET_NAME}' now...")
            s3.create_bucket(Bucket=BUCKET_NAME)
            print("✅ Bucket created successfully.")
        else:
            print(f"❌ Unexpected connection failure: {e}")
            return

    print("-" * 50)

    # ==========================================
    # 3. ADVANCED WRITES (UPLOAD & PUT OBJECT)
    # ==========================================
    # Create temporary dummy files to mimic a local workspace
    local_file = "temp_report.csv"
    with open(local_file, "w") as f:
        f.write("id,timestamp,metric\n1,1719482400,0.94\n2,1719482460,0.97")

    # Upload A: Stream a physical file into a virtual directory prefix
    target_key_1 = "raw-data/2026/monthly_report.csv"
    s3.upload_file(Filename=local_file, Bucket=BUCKET_NAME, Key=target_key_1)
    print(f"📤 Uploaded physical file to: {target_key_1}")

    # Upload B: Put raw data directly from in-memory buffers (no local storage footprint)
    memory_buffer = io.BytesIO(b"LOGSTREAM: Process initiated, jobs running smoothly.")
    target_key_2 = "logs/system_status.log"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=target_key_2,
        Body=memory_buffer,
        ContentType="text/plain"
    )
    print(f"📤 Uploaded in-memory data to: {target_key_2}")

    print("-" * 50)

    # ==========================================
    # 4. READ & METADATA EXAMINATION
    # ==========================================
    # Verify file sizes and content metadata without pulling down payloads
    meta_response = s3.head_object(Bucket=BUCKET_NAME, Key=target_key_2)
    print(f"ℹ️ Verified {target_key_2}:")
    print(f"   Size: {meta_response['ContentLength']} bytes")
    print(f"   Type: {meta_response['ContentType']}")

    # Stream the content directly down to application standard output
    download_stream = s3.get_object(Bucket=BUCKET_NAME, Key=target_key_2)
    file_contents = download_stream['Body'].read().decode('utf-8')
    print(f"📥 Downloaded Payload:\n   \"{file_contents}\"")

    print("-" * 50)

    # ==========================================
    # 5. SCOPED LISTING & PARSING
    # ==========================================
    # List objects nested only within a specific virtual folder prefix
    target_prefix = "raw-data/"
    print(f"🔍 Scanning files under prefix '{target_prefix}'...")
    
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=target_prefix)

    for page in pages:
        if 'Contents' in page:
            for item in page['Contents']:
                print(f"   📍 Found: {item['Key']} | Size: {item['Size']} bytes")
        else:
            print("   No objects found matching prefix.")

    print("-" * 50)

    # ==========================================
    # 6. BULK DELETION & WORKSPACE TEARDOWN
    # ==========================================
    print("🧹 Cleaning environment...")
    
    # Clean up local filesystem file
    if os.path.exists(local_file):
        os.remove(local_file)

    # Clean up remote object storage using structural batch deletion
    objects_to_delete = {'Objects': [{'Key': target_key_1}, {'Key': target_key_2}]}
    delete_summary = s3.delete_objects(Bucket=BUCKET_NAME, Delete=objects_to_delete)
    
    print(f"🗑️ Cleaned {len(delete_summary.get('Deleted', []))} remote objects from storage.")

    # Remove bucket container
    s3.delete_bucket(Bucket=BUCKET_NAME)
    print(f"🗑️ Destroyed empty container '{BUCKET_NAME}'.")
    print("\n💯 Process complete. Total backend execution successful without manual UI interaction.")

if __name__ == "__main__":
    run_pipeline()