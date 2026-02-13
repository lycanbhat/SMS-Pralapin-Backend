"""AWS S3: photos and PDF receipts."""
import uuid
from typing import BinaryIO, AsyncGenerator
import asyncio
from io import BytesIO
from app.config import settings
import boto3
from botocore.exceptions import ClientError

_s3 = None


def get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
        )
    return _s3


async def upload_photo_to_s3(
    file,
    *,
    student_id: str,
    activity_id: str,
) -> tuple[str, str]:
    """Upload photo; return (public_url, s3_key)."""
    ext = (file.filename or "").split(".")[-1] or "jpg"
    key = f"photos/{student_id}/{activity_id}/{uuid.uuid4().hex}.{ext}"
    bucket = settings.s3_bucket_photos
    content = await file.read()
    get_s3().put_object(Bucket=bucket, Key=key, Body=content, ContentType=file.content_type or "image/jpeg")
    url = f"https://{bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"
    return url, key


async def upload_receipt_to_s3(key: str, body: bytes, content_type: str = "application/pdf") -> str:
    bucket = settings.s3_bucket_receipts
    get_s3().put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
    return f"https://{bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"


async def upload_album_photo_to_s3(
    file,
    *,
    album_id: str,
) -> tuple[str, str]:
    """Upload photo for album; return (public_url, s3_key)."""
    ext = (file.filename or "").split(".")[-1] or "jpg"
    key = f"gallery/{album_id}/{uuid.uuid4().hex}.{ext}"
    bucket = settings.s3_bucket_photos
    content = await file.read()
    get_s3().put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
        ContentType=file.content_type or "image/jpeg",
    )
    url = f"https://{bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"
    return url, key


async def delete_from_s3(key: str, bucket: str = settings.s3_bucket_photos) -> None:
    """Delete object from S3."""
    try:
        get_s3().delete_object(Bucket=bucket, Key=key)
    except ClientError:
        pass


def _upload_banner_sync(file: bytes, key: str, content_type: str) -> None:
    get_s3().put_object(
        Bucket=settings.s3_bucket_photos,
        Key=key,
        Body=file,
        ContentType=content_type or "image/jpeg",
    )


async def upload_banner_to_s3(file: bytes, filename: str, content_type: str) -> tuple[str, str]:
    """Upload banner image; return (public_url, s3_key)."""
    import asyncio
    ext = (filename or "").split(".")[-1] or "jpg"
    key = f"banners/{uuid.uuid4().hex}.{ext}"
    bucket = settings.s3_bucket_photos
    await asyncio.to_thread(_upload_banner_sync, file, key, content_type or "image/jpeg")
    url = f"https://{bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"
    return url, key