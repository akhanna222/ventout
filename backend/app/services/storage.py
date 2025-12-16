import os
import uuid
from typing import Optional

import boto3

S3_BUCKET = os.getenv("S3_BUCKET")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_PREFIX = os.getenv("S3_PREFIX", "voice-notes")


def _client():
    session = boto3.session.Session()
    return session.client("s3", region_name=S3_REGION, endpoint_url=S3_ENDPOINT)


def upload_raw_audio(user_id: int, payload: bytes, content_type: str | None = None) -> Optional[str]:
    if not S3_BUCKET:
        return None

    key = f"{S3_PREFIX}/{user_id}/{uuid.uuid4()}.bin"
    client = _client()
    client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=payload,
        ContentType=content_type or "application/octet-stream",
    )
    return f"s3://{S3_BUCKET}/{key}"
