"""Tests for the recipe image upload + serving routes (local-fallback mode)."""
import pytest
from fastapi.testclient import TestClient

import storage
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("AWS_S3_BUCKET_NAME", raising=False)
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path)
    return TestClient(app)


def test_upload_returns_absolute_image_url(client):
    res = client.post(
        "/recipes/upload-image",
        files={"file": ("pic.png", b"pngbytes", "image/png")},
    )
    assert res.status_code == 201
    url = res.json()["image_url"]
    assert url.startswith("http")
    assert "/recipes/images/recipes/" in url


def test_upload_then_serve_roundtrips_bytes(client):
    url = client.post(
        "/recipes/upload-image",
        files={"file": ("pic.png", b"pngbytes", "image/png")},
    ).json()["image_url"]
    path = url.split("/recipes/images/", 1)[1]

    res = client.get(f"/recipes/images/{path}")
    assert res.status_code == 200
    assert res.content == b"pngbytes"
    assert res.headers["content-type"].startswith("image/png")


def test_upload_rejects_non_image(client):
    res = client.post(
        "/recipes/upload-image",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 415


def test_upload_rejects_oversized_file(client):
    big = b"x" * (5 * 1024 * 1024 + 1)
    res = client.post(
        "/recipes/upload-image",
        files={"file": ("big.png", big, "image/png")},
    )
    assert res.status_code == 413


def test_serve_missing_image_returns_404(client):
    res = client.get("/recipes/images/recipes/missing.png")
    assert res.status_code == 404


def test_upload_requires_api_key_when_configured(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    res = client.post(
        "/recipes/upload-image",
        files={"file": ("pic.png", b"pngbytes", "image/png")},
    )
    assert res.status_code == 401
