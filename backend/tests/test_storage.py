"""Tests for the image storage abstraction (local-filesystem fallback mode)."""
import importlib

import pytest


@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    """Reload ``storage`` in local-fallback mode with a temp media dir."""
    monkeypatch.delenv("AWS_S3_BUCKET_NAME", raising=False)
    import storage
    importlib.reload(storage)
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path)
    return storage


def test_save_image_returns_prefixed_key_with_extension(local_storage):
    key = local_storage.save_image(b"\xff\xd8\xff\x00", "image/jpeg")
    assert key.startswith("recipes/")
    assert key.endswith(".jpg")


def test_save_and_open_roundtrips_bytes_and_content_type(local_storage):
    key = local_storage.save_image(b"pngbytes", "image/png")
    data, content_type = local_storage.open_image(key)
    assert data == b"pngbytes"
    assert content_type == "image/png"


def test_save_image_rejects_non_image_content_type(local_storage):
    with pytest.raises(ValueError):
        local_storage.save_image(b"hello", "text/plain")


def test_open_image_missing_key_raises(local_storage):
    with pytest.raises(FileNotFoundError):
        local_storage.open_image("recipes/does-not-exist.jpg")
