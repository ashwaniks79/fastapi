# # app/services/storage.py
# import os
# import io
# import tempfile
# import boto3
# from fastapi.concurrency import run_in_threadpool

# SPACES_REGION = os.getenv("SPACES_REGION")
# SPACES_ENDPOINT = os.getenv("SPACES_ENDPOINT")
# SPACES_KEY = os.getenv("SPACES_KEY")
# SPACES_SECRET = os.getenv("SPACES_SECRET")
# SPACES_BUCKET = os.getenv("SPACES_BUCKET")

# _session = boto3.session.Session()
# _s3 = _session.client(
#     "s3",
#     region_name=SPACES_REGION,
#     endpoint_url=SPACES_ENDPOINT,
#     aws_access_key_id=SPACES_KEY,
#     aws_secret_access_key=SPACES_SECRET
# )

# # New method for AI/project usage
# # async def upload_bytes(key: str, content: bytes, content_type: str, acl: str = "private"):
# #     await run_in_threadpool(
# #         _s3.put_object,
# #         Bucket=SPACES_BUCKET,
# #         Key=key,
# #         Body=content,
# #         ContentType=content_type,
# #         ACL=acl
# #     )
# #     return key
# async def upload_bytes(key: str, content: bytes, content_type: str, acl: str = "public-read"):
#     await run_in_threadpool(
#         _s3.put_object,
#         Bucket=SPACES_BUCKET,
#         Key=key,
#         Body=content,
#         ContentType=content_type,
#         ACL=acl
#     )
#     file_url = None
#     if acl == "public-read":
#         file_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{key}"
#     return {"key": key, "url": file_url}

# # Old method kept for backward compatibility
# async def upload_file_to_spaces(file_obj, filename: str, content_type: str):
#     await run_in_threadpool(
#         _s3.upload_fileobj,
#         Fileobj=io.BytesIO(file_obj.read() if hasattr(file_obj, "read") else file_obj),
#         Bucket=SPACES_BUCKET,
#         Key=filename,
#         ExtraArgs={"ACL": "public-read", "ContentType": content_type}
#     )
#     # return f"{SPACES_ENDPOINT}/{SPACES_BUCKET}/{filename}"
#     return f"{SPACES_ENDPOINT}/{filename}"


# async def generate_presigned_url(key: str, expires_in: int = 3600):
#     return await run_in_threadpool(
#         _s3.generate_presigned_url,
#         ClientMethod='get_object',
#         Params={"Bucket": SPACES_BUCKET, "Key": key},
#         ExpiresIn=expires_in
#     )

# async def download_to_tmpfile(key: str) -> str:
#     resp = await run_in_threadpool(_s3.get_object, Bucket=SPACES_BUCKET, Key=key)
#     body = resp['Body'].read()
#     tmp = tempfile.NamedTemporaryFile(delete=False)
#     tmp.write(body)
#     tmp.close()
#     return tmp.name

# async def delete_object(key: str):
#     await run_in_threadpool(_s3.delete_object, Bucket=SPACES_BUCKET, Key=key)
# app/services/storage.py
import os
import io
import tempfile
import boto3
from fastapi.concurrency import run_in_threadpool

SPACES_REGION = os.getenv("SPACES_REGION")
SPACES_ENDPOINT = os.getenv("SPACES_ENDPOINT")  # can be region or bucket endpoint
SPACES_KEY = os.getenv("SPACES_KEY")
SPACES_SECRET = os.getenv("SPACES_SECRET")
SPACES_BUCKET = os.getenv("SPACES_BUCKET")

_session = boto3.session.Session()
_s3 = _session.client(
    "s3",
    region_name=SPACES_REGION,
    endpoint_url=SPACES_ENDPOINT,
    aws_access_key_id=SPACES_KEY,
    aws_secret_access_key=SPACES_SECRET
)

def _build_public_url(key: str) -> str:
    # Standard Spaces public URL pattern
    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{key}"

async def upload_bytes(key: str, content: bytes, content_type: str, acl: str = "private"):
    await run_in_threadpool(
        _s3.put_object,
        Bucket=SPACES_BUCKET,
        Key=key,
        Body=content,
        ContentType=content_type,
        ACL=acl
    )
    file_url = _build_public_url(key) if acl == "public-read" else None
    return {"key": key, "url": file_url}

# Old method kept for backward compatibility
async def upload_file_to_spaces(file_obj, filename: str, content_type: str):
    await run_in_threadpool(
        _s3.upload_fileobj,
        Fileobj=io.BytesIO(file_obj.read() if hasattr(file_obj, "read") else file_obj),
        Bucket=SPACES_BUCKET,
        Key=filename,
        ExtraArgs={"ACL": "public-read", "ContentType": content_type}
    )
    # If SPACES_ENDPOINT is a bucket URL, this works. Otherwise switch to _build_public_url(filename)
    return f"{SPACES_ENDPOINT}/{filename}"

async def generate_presigned_url(key: str, expires_in: int = 3600):
    return await run_in_threadpool(
        _s3.generate_presigned_url,
        ClientMethod='get_object',
        Params={"Bucket": SPACES_BUCKET, "Key": key},
        ExpiresIn=expires_in
    )

async def download_to_tmpfile(key: str) -> str:
    resp = await run_in_threadpool(_s3.get_object, Bucket=SPACES_BUCKET, Key=key)
    body = resp['Body'].read()
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(body)
    tmp.close()
    return tmp.name

async def delete_object(key: str):
    await run_in_threadpool(_s3.delete_object, Bucket=SPACES_BUCKET, Key=key)
