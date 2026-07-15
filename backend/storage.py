"""Image storage abstraction.

Persists uploaded recipe images either to a Railway S3-compatible object storage
bucket (production) or to a local ``media/`` directory (local dev / CI). The mode
is chosen by the presence of the ``AWS_S3_BUCKET_NAME`` environment variable, which
Railway populates from the bucket credentials.

Images are addressed by an opaque object *key* (e.g. ``recipes/<uuid>.jpg``). The
key is stored (indirectly, as part of ``image_url``) and used to stream the bytes
back out.
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

# Absolute path so the location is stable regardless of the working directory.
MEDIA_DIR = Path(__file__).resolve().parent / "media"

# Content types we accept, mapped to the extension used for the stored key.
_EXT_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
}
_CONTENT_TYPE_BY_EXT = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}


def _bucket_name() -> str | None:
    return os.environ.get("AWS_S3_BUCKET_NAME") or None


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("AWS_ENDPOINT_URL"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_DEFAULT_REGION"),
    )


def _key_for(content_type: str) -> str:
    ext = _EXT_BY_CONTENT_TYPE.get(content_type.lower())
    if ext is None:
        raise ValueError(f"Unsupported image content type: {content_type!r}")
    return f"recipes/{uuid4().hex}{ext}"


def save_image(data: bytes, content_type: str) -> str:
    """Persist ``data`` and return its object key. Raises ``ValueError`` for
    non-image content types."""
    key = _key_for(content_type)
    bucket = _bucket_name()
    if bucket:
        _s3_client().put_object(
            Bucket=bucket, Key=key, Body=data, ContentType=content_type
        )
    else:
        path = MEDIA_DIR / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return key


def open_image(key: str) -> tuple[bytes, str]:
    """Return ``(bytes, content_type)`` for a stored key. Raises
    ``FileNotFoundError`` if the key does not exist."""
    ext = Path(key).suffix.lower()
    content_type = _CONTENT_TYPE_BY_EXT.get(ext, "application/octet-stream")
    bucket = _bucket_name()
    if bucket:
        client = _s3_client()
        try:
            obj = client.get_object(Bucket=bucket, Key=key)
        except client.exceptions.NoSuchKey as exc:  # pragma: no cover
            raise FileNotFoundError(key) from exc
        return obj["Body"].read(), obj.get("ContentType", content_type)
    path = MEDIA_DIR / key
    if not path.is_file():
        raise FileNotFoundError(key)
    return path.read_bytes(), content_type
