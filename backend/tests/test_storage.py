"""Unit tests for MinIO client and StorageManager."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from minio.error import S3Error

from src.storage.minio_client import MinIOClient, StorageError, DEFAULT_BUCKET
from src.storage.storage_manager import StorageManager, StorageBackend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset MinIOClient singleton between tests."""
    MinIOClient.reset()
    yield
    MinIOClient.reset()


@pytest.fixture()
def mock_minio():
    """Patch the Minio constructor so no real connection is made."""
    with patch("src.storage.minio_client.Minio") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture()
def minio_client(mock_minio) -> MinIOClient:
    """Return a MinIOClient backed by a mocked Minio instance."""
    client = MinIOClient()
    return client


@pytest.fixture()
def tmp_file(tmp_path: Path) -> Path:
    """Create a small temporary file for upload tests."""
    p = tmp_path / "sample.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # fake JPEG header
    return p


# ---------------------------------------------------------------------------
# MinIOClient tests
# ---------------------------------------------------------------------------


class TestMinIOClientInit:
    def test_singleton_returns_same_instance(self, mock_minio):
        a = MinIOClient()
        b = MinIOClient()
        assert a is b

    def test_reset_creates_new_instance(self, mock_minio):
        a = MinIOClient()
        MinIOClient.reset()
        b = MinIOClient()
        assert a is not b

    def test_client_property(self, minio_client, mock_minio):
        assert minio_client.client is mock_minio

    def test_default_bucket(self, minio_client):
        assert minio_client.bucket == "kalye-images"


class TestInitializeBucket:
    def test_creates_bucket_when_not_exists(self, minio_client, mock_minio):
        mock_minio.bucket_exists.return_value = False
        minio_client.initialize_bucket()
        mock_minio.make_bucket.assert_called_once_with("kalye-images")

    def test_skips_when_bucket_exists(self, minio_client, mock_minio):
        mock_minio.bucket_exists.return_value = True
        minio_client.initialize_bucket()
        mock_minio.make_bucket.assert_not_called()

    def test_custom_bucket_name(self, minio_client, mock_minio):
        mock_minio.bucket_exists.return_value = False
        minio_client.initialize_bucket("custom-bucket")
        mock_minio.make_bucket.assert_called_once_with("custom-bucket")

    def test_raises_storage_error_on_failure(self, minio_client, mock_minio):
        mock_minio.bucket_exists.side_effect = Exception("connection refused")
        with pytest.raises(StorageError) as exc_info:
            minio_client.initialize_bucket()
        assert exc_info.value.operation == "initialize_bucket"


class TestUploadFile:
    def test_upload_returns_object_name(self, minio_client, mock_minio, tmp_file):
        result = minio_client.upload_file(tmp_file, "uploads/test.jpg")
        assert result == "uploads/test.jpg"
        mock_minio.put_object.assert_called_once()

    def test_upload_passes_metadata(self, minio_client, mock_minio, tmp_file):
        minio_client.upload_file(tmp_file, "test.jpg", metadata={"source": "upload"})
        call_kwargs = mock_minio.put_object.call_args
        assert call_kwargs.kwargs.get("metadata") == {"source": "upload"} or \
               call_kwargs[1].get("metadata") == {"source": "upload"}

    def test_upload_raises_on_failure(self, minio_client, mock_minio, tmp_file):
        mock_minio.put_object.side_effect = Exception("write error")
        with pytest.raises(StorageError) as exc_info:
            minio_client.upload_file(tmp_file, "test.jpg")
        assert exc_info.value.operation == "upload_file"


class TestPresignedUrl:
    def test_returns_url_string(self, minio_client, mock_minio):
        mock_minio.presigned_get_object.return_value = "https://minio:9000/kalye-images/test.jpg?token=abc"
        url = minio_client.generate_presigned_url("test.jpg")
        assert url.startswith("https://")
        mock_minio.presigned_get_object.assert_called_once()

    def test_custom_expiry(self, minio_client, mock_minio):
        mock_minio.presigned_get_object.return_value = "https://example.com"
        minio_client.generate_presigned_url("test.jpg", expiry_seconds=7200)
        call_kwargs = mock_minio.presigned_get_object.call_args
        assert call_kwargs.kwargs.get("expires") == timedelta(seconds=7200) or \
               call_kwargs[1].get("expires") == timedelta(seconds=7200)

    def test_raises_on_failure(self, minio_client, mock_minio):
        mock_minio.presigned_get_object.side_effect = Exception("auth error")
        with pytest.raises(StorageError):
            minio_client.generate_presigned_url("test.jpg")


class TestDeleteFile:
    def test_delete_returns_true(self, minio_client, mock_minio):
        result = minio_client.delete_file("test.jpg")
        assert result is True
        mock_minio.remove_object.assert_called_once_with(
            bucket_name="kalye-images", object_name="test.jpg"
        )

    def test_delete_raises_on_failure(self, minio_client, mock_minio):
        mock_minio.remove_object.side_effect = Exception("not found")
        with pytest.raises(StorageError) as exc_info:
            minio_client.delete_file("missing.jpg")
        assert exc_info.value.operation == "delete_file"


class TestListFiles:
    def test_list_returns_objects(self, minio_client, mock_minio):
        obj = SimpleNamespace(
            object_name="img/photo.jpg",
            size=1024,
            last_modified=datetime(2025, 1, 1, tzinfo=timezone.utc),
            etag="abc123",
        )
        mock_minio.list_objects.return_value = iter([obj])
        results = minio_client.list_files(prefix="img/")
        assert len(results) == 1
        assert results[0]["name"] == "img/photo.jpg"
        assert results[0]["size"] == 1024

    def test_list_respects_max_keys(self, minio_client, mock_minio):
        objs = [
            SimpleNamespace(object_name=f"file{i}.jpg", size=100, last_modified=None, etag="x")
            for i in range(10)
        ]
        mock_minio.list_objects.return_value = iter(objs)
        results = minio_client.list_files(max_keys=3)
        assert len(results) == 3

    def test_list_raises_on_failure(self, minio_client, mock_minio):
        mock_minio.list_objects.side_effect = Exception("timeout")
        with pytest.raises(StorageError):
            minio_client.list_files()


class TestFileExists:
    def test_returns_true_when_exists(self, minio_client, mock_minio):
        mock_minio.stat_object.return_value = SimpleNamespace()
        assert minio_client.file_exists("test.jpg") is True

    def test_returns_false_when_not_exists(self, minio_client, mock_minio):
        error = S3Error(
            code="NoSuchKey",
            message="not found",
            resource="/kalye-images/missing.jpg",
            request_id="req1",
            host_id="host1",
            response=MagicMock(),
        )
        mock_minio.stat_object.side_effect = error
        assert minio_client.file_exists("missing.jpg") is False

    def test_raises_on_other_s3_error(self, minio_client, mock_minio):
        error = S3Error(
            code="AccessDenied",
            message="forbidden",
            resource="/kalye-images/secret.jpg",
            request_id="req1",
            host_id="host1",
            response=MagicMock(),
        )
        mock_minio.stat_object.side_effect = error
        with pytest.raises(StorageError):
            minio_client.file_exists("secret.jpg")


class TestGetFileMetadata:
    def test_returns_metadata_dict(self, minio_client, mock_minio):
        stat = SimpleNamespace(
            object_name="test.jpg",
            size=2048,
            etag="etag123",
            content_type="image/jpeg",
            last_modified=datetime(2025, 6, 15, tzinfo=timezone.utc),
            metadata={"md5_checksum": "abc"},
        )
        mock_minio.stat_object.return_value = stat
        meta = minio_client.get_file_metadata("test.jpg")
        assert meta["name"] == "test.jpg"
        assert meta["size"] == 2048
        assert meta["content_type"] == "image/jpeg"
        assert meta["metadata"]["md5_checksum"] == "abc"

    def test_raises_on_failure(self, minio_client, mock_minio):
        mock_minio.stat_object.side_effect = Exception("gone")
        with pytest.raises(StorageError) as exc_info:
            minio_client.get_file_metadata("test.jpg")
        assert exc_info.value.operation == "get_file_metadata"


class TestNetworkFailure:
    def test_connection_error_raises_storage_error(self, minio_client, mock_minio, tmp_file):
        mock_minio.put_object.side_effect = ConnectionError("connection refused")
        with pytest.raises(StorageError):
            minio_client.upload_file(tmp_file, "test.jpg")

    def test_general_exception_wrapped(self, minio_client, mock_minio):
        mock_minio.remove_object.side_effect = RuntimeError("unexpected")
        with pytest.raises(StorageError):
            minio_client.delete_file("test.jpg")


class TestHealthCheck:
    def test_healthy(self, minio_client, mock_minio):
        mock_minio.list_buckets.return_value = []
        assert minio_client.health_check() is True

    def test_unhealthy(self, minio_client, mock_minio):
        mock_minio.list_buckets.side_effect = Exception("down")
        assert minio_client.health_check() is False


# ---------------------------------------------------------------------------
# StorageManager tests
# ---------------------------------------------------------------------------


class TestStorageManagerContentType:
    def test_detect_jpeg(self):
        assert StorageManager.detect_content_type(Path("photo.jpg")) == "image/jpeg"

    def test_detect_png(self):
        assert StorageManager.detect_content_type(Path("photo.png")) == "image/png"

    def test_detect_webp(self):
        assert StorageManager.detect_content_type(Path("photo.webp")) == "image/webp"

    def test_detect_unknown_returns_octet_stream(self):
        assert StorageManager.detect_content_type(Path("file.xyz123")) == "application/octet-stream"


class TestStorageManagerChecksum:
    def test_compute_md5(self, tmp_file):
        expected = hashlib.md5(tmp_file.read_bytes()).hexdigest()
        assert StorageManager.compute_md5(tmp_file) == expected

    def test_checksum_deterministic(self, tmp_file):
        a = StorageManager.compute_md5(tmp_file)
        b = StorageManager.compute_md5(tmp_file)
        assert a == b


class TestStorageManagerLocalBackend:
    def test_upload_and_download(self, tmp_path, tmp_file):
        local_root = tmp_path / "store"
        mgr = StorageManager(backend=StorageBackend.LOCAL, local_root=local_root)

        obj_name = mgr.upload_image(tmp_file, "uploads/test.jpg")
        assert obj_name == "uploads/test.jpg"
        assert (local_root / "uploads" / "test.jpg").is_file()

        dest = tmp_path / "downloads" / "test.jpg"
        result = mgr.download_image("uploads/test.jpg", dest)
        assert result.is_file()
        assert result.read_bytes() == tmp_file.read_bytes()

    def test_delete_image(self, tmp_path, tmp_file):
        local_root = tmp_path / "store"
        mgr = StorageManager(backend=StorageBackend.LOCAL, local_root=local_root)
        mgr.upload_image(tmp_file, "test.jpg")
        assert mgr.delete_image("test.jpg") is True
        assert not (local_root / "test.jpg").is_file()

    def test_get_url_returns_file_uri(self, tmp_path, tmp_file):
        local_root = tmp_path / "store"
        mgr = StorageManager(backend=StorageBackend.LOCAL, local_root=local_root)
        mgr.upload_image(tmp_file, "test.jpg")
        url = mgr.get_url("test.jpg")
        assert url.startswith("file://")

    def test_upload_nonexistent_raises(self, tmp_path):
        mgr = StorageManager(backend=StorageBackend.LOCAL, local_root=tmp_path / "store")
        with pytest.raises(StorageError):
            mgr.upload_image(Path("/nonexistent/file.jpg"), "test.jpg")

    def test_checksum_verified_on_download(self, tmp_path, tmp_file):
        local_root = tmp_path / "store"
        mgr = StorageManager(backend=StorageBackend.LOCAL, local_root=local_root)
        mgr.upload_image(tmp_file, "test.jpg")

        # Corrupt the stored file after upload
        stored = local_root / "test.jpg"
        stored.write_bytes(b"corrupted data")

        dest = tmp_path / "dl" / "test.jpg"
        with pytest.raises(StorageError, match="Checksum mismatch"):
            mgr.download_image("test.jpg", dest, verify_checksum=True)


class TestStorageManagerMinIOBackend:
    def test_upload_calls_minio_client(self, mock_minio, tmp_file):
        mgr = StorageManager(backend=StorageBackend.MINIO)
        mock_minio.put_object.return_value = None
        result = mgr.upload_image(tmp_file, "uploads/img.jpg", metadata={"user": "test"})
        assert result == "uploads/img.jpg"
        mock_minio.put_object.assert_called_once()

    def test_get_url_calls_presigned(self, mock_minio):
        mgr = StorageManager(backend=StorageBackend.MINIO)
        mock_minio.presigned_get_object.return_value = "https://minio/url"
        url = mgr.get_url("test.jpg", expiry_seconds=600)
        assert url == "https://minio/url"
