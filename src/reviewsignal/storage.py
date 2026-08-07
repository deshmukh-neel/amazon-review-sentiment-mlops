from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from google.cloud import storage


class StorageUriError(ValueError):
    """Raised when an artifact URI cannot be handled safely."""


def parse_gcs_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    object_name = parsed.path.lstrip("/")
    if parsed.scheme != "gs" or not parsed.netloc or not object_name:
        raise StorageUriError(f"invalid GCS object URI: {uri}")
    return parsed.netloc, object_name


def upload_file(source: Path, destination_uri: str, *, client: Any | None = None) -> None:
    bucket_name, object_name = parse_gcs_uri(destination_uri)
    storage_client = client or storage.Client()
    storage_client.bucket(bucket_name).blob(object_name).upload_from_filename(str(source))


def download_uri(
    source_uri: str,
    destination: Path,
    *,
    client: Any | None = None,
) -> Path:
    if not source_uri.startswith("gs://"):
        source = Path(source_uri)
        if not source.is_file():
            raise StorageUriError(f"local artifact does not exist: {source}")
        return source

    bucket_name, object_name = parse_gcs_uri(source_uri)
    destination.parent.mkdir(parents=True, exist_ok=True)
    storage_client = client or storage.Client()
    storage_client.bucket(bucket_name).blob(object_name).download_to_filename(str(destination))
    return destination
