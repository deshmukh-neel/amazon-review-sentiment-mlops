from __future__ import annotations

import pytest

from reviewsignal.storage import StorageUriError, download_uri, parse_gcs_uri, upload_file


def test_parse_gcs_uri_requires_bucket_and_object() -> None:
    assert parse_gcs_uri("gs://private-models/candidates/v1/model.joblib") == (
        "private-models",
        "candidates/v1/model.joblib",
    )

    with pytest.raises(StorageUriError):
        parse_gcs_uri("gs://bucket-only")
    with pytest.raises(StorageUriError):
        parse_gcs_uri("https://example.com/model.joblib")


def test_fake_gcs_upload_and_download_round_trip(tmp_path, fake_storage) -> None:
    source = tmp_path / "model.joblib"
    source.write_bytes(b"verified model bytes")
    uri = "gs://private-models/candidates/model.joblib"

    upload_file(source, uri, client=fake_storage)
    destination = tmp_path / "downloaded.joblib"
    resolved = download_uri(uri, destination, client=fake_storage)

    assert resolved == destination
    assert destination.read_bytes() == b"verified model bytes"


def test_local_download_returns_existing_path_without_copy(tmp_path) -> None:
    source = tmp_path / "local-model.joblib"
    source.write_bytes(b"local")

    assert download_uri(str(source), tmp_path / "unused") == source
