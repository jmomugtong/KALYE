"""MinIO object storage client with retry logic and singleton pattern."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from minio import Minio
from minio.error import S3Error
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from urllib3.exceptions import HTTPError

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "kalye-images"


class StorageError(Exception):
    """Custom exception for storage operations."""

    def __init__(self, message: str, operation: str | None = None, cause: Exception | None = None):
        self.operation = operation
        self.cause = cause
        super().__init__(message)


class MinIOClient:
    """Singleton MinIO client wrapper with retry and logging."""

    _instance: MinIOClient | None = None
    _client: Minio | None = None

    def __new__(cls) -> MinIOClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._client is not None:
            return
        settings = get_settings()
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.s3_bucket_name
        logger.info("MinIO client initialized for endpoint %s", settings.minio_endpoint)

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None
        cls._client = None

    @property
    def client(self) -> Minio:
        assert self._client is not None
        return self._client

    @property
    def bucket(self) -> str:
        return self._bucket

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((S3Error, HTTPError, ConnectionError)),
        reraise=True,
    )
    def initialize_bucket(self, bucket_name: str | None = None) -> None:
        """Create a bucket if it does not already exist."""
        name = bucket_name or self._bucket
        try:
            if not self.client.bucket_exists(name):
                self.client.make_bucket(name)
                logger.info("Created bucket: %s", name)
            else:
                logger.debug("Bucket already exists: %s", name)
        except Exception as exc:
            logger.error("Failed to initialize bucket %s: %s", name, exc)
            raise StorageError(
                f"Failed to initialize bucket '{name}'",
                operation="initialize_bucket",
                cause=exc,
            ) from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((S3Error, HTTPError, ConnectionError)),
        reraise=True,
    )
    def upload_file(
        self,
        file_path: Path,
        object_name: str,
        metadata: dict[str, str] | None = None,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to MinIO and return the object name."""
        try:
            file_path = Path(file_path)
            file_size = file_path.stat().st_size
            with open(file_path, "rb") as fh:
                self.client.put_object(
                    bucket_name=self._bucket,
                    object_name=object_name,
                    data=fh,
                    length=file_size,
                    content_type=content_type,
                    metadata=metadata or {},
                )
            logger.info("Uploaded %s -> %s/%s (%d bytes)", file_path, self._bucket, object_name, file_size)
            return object_name
        except Exception as exc:
            logger.error("Upload failed for %s: %s", object_name, exc)
            raise StorageError(
                f"Failed to upload '{object_name}'",
                operation="upload_file",
                cause=exc,
            ) from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((S3Error, HTTPError, ConnectionError)),
        reraise=True,
    )
    def download_file(self, object_name: str, destination: Path) -> Path:
        """Download an object from MinIO to a local path."""
        try:
            destination = Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            self.client.fget_object(
                bucket_name=self._bucket,
                object_name=object_name,
                file_path=str(destination),
            )
            logger.info("Downloaded %s/%s -> %s", self._bucket, object_name, destination)
            return destination
        except Exception as exc:
            logger.error("Download failed for %s: %s", object_name, exc)
            raise StorageError(
                f"Failed to download '{object_name}'",
                operation="download_file",
                cause=exc,
            ) from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((S3Error, HTTPError, ConnectionError)),
        reraise=True,
    )
    def generate_presigned_url(self, object_name: str, expiry_seconds: int = 3600) -> str:
        """Generate a presigned URL for temporary access to an object."""
        from datetime import timedelta

        try:
            url = self.client.presigned_get_object(
                bucket_name=self._bucket,
                object_name=object_name,
                expires=timedelta(seconds=expiry_seconds),
            )
            logger.info("Generated presigned URL for %s (expires in %ds)", object_name, expiry_seconds)
            return url
        except Exception as exc:
            logger.error("Presigned URL generation failed for %s: %s", object_name, exc)
            raise StorageError(
                f"Failed to generate presigned URL for '{object_name}'",
                operation="generate_presigned_url",
                cause=exc,
            ) from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((S3Error, HTTPError, ConnectionError)),
        reraise=True,
    )
    def delete_file(self, object_name: str) -> bool:
        """Delete an object from MinIO. Returns True on success."""
        try:
            self.client.remove_object(
                bucket_name=self._bucket,
                object_name=object_name,
            )
            logger.info("Deleted %s/%s", self._bucket, object_name)
            return True
        except Exception as exc:
            logger.error("Delete failed for %s: %s", object_name, exc)
            raise StorageError(
                f"Failed to delete '{object_name}'",
                operation="delete_file",
                cause=exc,
            ) from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((S3Error, HTTPError, ConnectionError)),
        reraise=True,
    )
    def list_files(self, prefix: str = "", max_keys: int = 1000) -> list[dict[str, Any]]:
        """List objects in the bucket with an optional prefix."""
        try:
            objects = self.client.list_objects(
                bucket_name=self._bucket,
                prefix=prefix or None,
            )
            results: list[dict[str, Any]] = []
            for obj in objects:
                if len(results) >= max_keys:
                    break
                results.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag,
                })
            logger.info("Listed %d objects with prefix='%s'", len(results), prefix)
            return results
        except Exception as exc:
            logger.error("List failed for prefix='%s': %s", prefix, exc)
            raise StorageError(
                f"Failed to list objects with prefix '{prefix}'",
                operation="list_files",
                cause=exc,
            ) from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((S3Error, HTTPError, ConnectionError)),
        reraise=True,
    )
    def file_exists(self, object_name: str) -> bool:
        """Check if an object exists in the bucket."""
        try:
            self.client.stat_object(
                bucket_name=self._bucket,
                object_name=object_name,
            )
            logger.debug("Object exists: %s/%s", self._bucket, object_name)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                logger.debug("Object does not exist: %s/%s", self._bucket, object_name)
                return False
            raise StorageError(
                f"Failed to check existence of '{object_name}'",
                operation="file_exists",
                cause=exc,
            ) from exc
        except Exception as exc:
            logger.error("Existence check failed for %s: %s", object_name, exc)
            raise StorageError(
                f"Failed to check existence of '{object_name}'",
                operation="file_exists",
                cause=exc,
            ) from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((S3Error, HTTPError, ConnectionError)),
        reraise=True,
    )
    def get_file_metadata(self, object_name: str) -> dict[str, Any]:
        """Retrieve metadata for an object."""
        try:
            stat = self.client.stat_object(
                bucket_name=self._bucket,
                object_name=object_name,
            )
            metadata: dict[str, Any] = {
                "name": stat.object_name,
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "metadata": dict(stat.metadata) if stat.metadata else {},
            }
            logger.info("Retrieved metadata for %s", object_name)
            return metadata
        except Exception as exc:
            logger.error("Metadata retrieval failed for %s: %s", object_name, exc)
            raise StorageError(
                f"Failed to get metadata for '{object_name}'",
                operation="get_file_metadata",
                cause=exc,
            ) from exc

    def health_check(self) -> bool:
        """Check MinIO connectivity by listing buckets."""
        try:
            self.client.list_buckets()
            logger.debug("MinIO health check passed")
            return True
        except Exception as exc:
            logger.warning("MinIO health check failed: %s", exc)
            return False
