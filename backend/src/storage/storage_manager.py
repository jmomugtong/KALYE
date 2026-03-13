"""Storage abstraction layer supporting MinIO and local filesystem backends."""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import shutil
from enum import Enum
from pathlib import Path
from typing import Any

from src.storage.minio_client import MinIOClient, StorageError

logger = logging.getLogger(__name__)


class StorageBackend(str, Enum):
    MINIO = "minio"
    LOCAL = "local"


class StorageManager:
    """High-level storage abstraction with content-type detection and checksum validation."""

    def __init__(
        self,
        backend: StorageBackend = StorageBackend.MINIO,
        local_root: Path | None = None,
    ) -> None:
        self._backend = backend
        if backend == StorageBackend.MINIO:
            self._minio = MinIOClient()
        else:
            self._local_root = Path(local_root or "/tmp/kalye-storage")
            self._local_root.mkdir(parents=True, exist_ok=True)
            self._minio = None  # type: ignore[assignment]
        logger.info("StorageManager initialized with backend=%s", backend.value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upload_image(
        self,
        file_path: Path,
        object_name: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload an image file, auto-detecting content type and attaching a SHA-256 checksum.

        Returns the object name / key of the stored file.
        """
        file_path = Path(file_path)
        if not file_path.is_file():
            raise StorageError(f"Source file does not exist: {file_path}", operation="upload_image")

        content_type = self.detect_content_type(file_path)
        checksum = self.compute_checksum(file_path)

        combined_metadata = dict(metadata or {})
        combined_metadata["sha256_checksum"] = checksum

        if self._backend == StorageBackend.MINIO:
            return self._minio.upload_file(
                file_path=file_path,
                object_name=object_name,
                metadata=combined_metadata,
                content_type=content_type,
            )
        else:
            return self._upload_local(file_path, object_name, combined_metadata)

    def download_image(self, object_name: str, destination: Path, verify_checksum: bool = True) -> Path:
        """Download an image and optionally verify its SHA-256 checksum."""
        destination = Path(destination)

        if self._backend == StorageBackend.MINIO:
            path = self._minio.download_file(object_name, destination)
            if verify_checksum:
                self._verify_checksum_minio(object_name, path)
            return path
        else:
            return self._download_local(object_name, destination, verify_checksum)

    def delete_image(self, object_name: str) -> bool:
        """Delete an image from storage."""
        if self._backend == StorageBackend.MINIO:
            return self._minio.delete_file(object_name)
        else:
            return self._delete_local(object_name)

    def get_url(self, object_name: str, expiry_seconds: int = 3600) -> str:
        """Get a URL for accessing the image."""
        if self._backend == StorageBackend.MINIO:
            return self._minio.generate_presigned_url(object_name, expiry_seconds)
        else:
            local_path = self._local_root / object_name
            return f"file://{local_path}"

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    @staticmethod
    def detect_content_type(file_path: Path) -> str:
        """Detect MIME type from file extension."""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type or "application/octet-stream"

    @staticmethod
    def compute_checksum(file_path: Path) -> str:
        """Compute SHA-256 hex digest of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    # ------------------------------------------------------------------
    # Local backend helpers
    # ------------------------------------------------------------------

    def _upload_local(self, file_path: Path, object_name: str, metadata: dict[str, str]) -> str:
        dest = self._local_root / object_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, dest)

        # Store metadata as a sidecar JSON file
        import json
        meta_path = dest.with_suffix(dest.suffix + ".meta")
        meta_path.write_text(json.dumps(metadata))

        logger.info("Local upload: %s -> %s", file_path, dest)
        return object_name

    def _download_local(self, object_name: str, destination: Path, verify_checksum: bool) -> Path:
        src = self._local_root / object_name
        if not src.is_file():
            raise StorageError(f"Object not found locally: {object_name}", operation="download_image")

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, destination)

        if verify_checksum:
            import json
            meta_path = src.with_suffix(src.suffix + ".meta")
            if meta_path.is_file():
                stored_meta = json.loads(meta_path.read_text())
                stored_checksum = stored_meta.get("sha256_checksum")
                if stored_checksum:
                    actual = self.compute_checksum(destination)
                    if actual != stored_checksum:
                        raise StorageError(
                            f"Checksum mismatch for '{object_name}': expected {stored_checksum}, got {actual}",
                            operation="download_image",
                        )

        logger.info("Local download: %s -> %s", src, destination)
        return destination

    def _delete_local(self, object_name: str) -> bool:
        target = self._local_root / object_name
        meta_path = target.with_suffix(target.suffix + ".meta")
        try:
            if target.is_file():
                target.unlink()
            if meta_path.is_file():
                meta_path.unlink()
            logger.info("Local delete: %s", object_name)
            return True
        except OSError as exc:
            raise StorageError(
                f"Failed to delete local file '{object_name}'",
                operation="delete_image",
                cause=exc,
            ) from exc

    def _verify_checksum_minio(self, object_name: str, downloaded_path: Path) -> None:
        """Verify downloaded file checksum against stored metadata."""
        try:
            metadata = self._minio.get_file_metadata(object_name)
            stored_meta = metadata.get("metadata", {})
            # MinIO may prefix custom metadata with "x-amz-meta-"
            stored_checksum = (
                stored_meta.get("sha256_checksum")
                or stored_meta.get("x-amz-meta-sha256_checksum")
                or stored_meta.get("X-Amz-Meta-Sha256_checksum")
            )
            if stored_checksum:
                actual = self.compute_checksum(downloaded_path)
                if actual != stored_checksum:
                    raise StorageError(
                        f"Checksum mismatch for '{object_name}': expected {stored_checksum}, got {actual}",
                        operation="download_image",
                    )
        except StorageError:
            raise
        except Exception:
            logger.warning("Could not verify checksum for %s, skipping", object_name)
