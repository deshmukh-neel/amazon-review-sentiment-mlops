from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from reviewsignal.ingestion import (
    load_jsonl_fixture,
    materialize_dataset,
    resolve_hugging_face_source,
)
from reviewsignal.manifests import DataManifest, read_manifest

FIXTURE_SHA = "f" * 64


def test_hugging_face_source_resolution_records_full_sha_and_lfs_checksums() -> None:
    full_sha = "ec149c1" + "0" * 33
    dataset_info = SimpleNamespace(
        sha=full_sha,
        siblings=[
            SimpleNamespace(
                rfilename="data/train-00000-of-00001.parquet",
                lfs=SimpleNamespace(sha256="a" * 64),
            ),
            SimpleNamespace(rfilename="README.md", lfs=None),
        ],
    )
    api = SimpleNamespace(dataset_info=lambda repo_id, revision: dataset_info)

    revision, checksums = resolve_hugging_face_source("mteb/amazon_polarity", "ec149c1", api=api)

    assert revision == full_sha
    assert checksums == {"data/train-00000-of-00001.parquet": "a" * 64}


def test_materialized_fixture_has_balanced_parquet_splits_and_manifest(
    tmp_path, fixture_path
) -> None:
    source_train, source_test = load_jsonl_fixture(fixture_path)

    manifest_path = materialize_dataset(
        source_train,
        source_test,
        output_dir=tmp_path / "processed",
        source="synthetic-fixture",
        source_revision="fixture-v1",
        source_checksums={"tiny_reviews.jsonl": FIXTURE_SHA},
        train_size=16,
        validation_size=8,
        test_size=8,
        seed=42,
        created_at=datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
    )

    manifest = read_manifest(manifest_path, DataManifest)
    assert manifest.row_counts == {"train": 16, "validation": 8, "test": 8}
    assert manifest.class_counts == {
        "train": {"0": 8, "1": 8},
        "validation": {"0": 4, "1": 4},
        "test": {"0": 4, "1": 4},
    }
    assert manifest.source_checksums == {"tiny_reviews.jsonl": FIXTURE_SHA}
    assert manifest.dataset_version.startswith("synthetic-fixture-")
    assert all(
        (tmp_path / "processed" / f"{name}.parquet").exists() for name in manifest.row_counts
    )


def test_materialized_dataset_can_publish_private_gcs_objects(
    tmp_path, fixture_path, fake_storage
) -> None:
    source_train, source_test = load_jsonl_fixture(fixture_path)

    manifest_path = materialize_dataset(
        source_train,
        source_test,
        output_dir=tmp_path / "processed",
        publish_prefix="gs://private-data/versions/fixture-v1",
        storage_client=fake_storage,
        source="synthetic-fixture",
        source_revision="fixture-v1",
        source_checksums={"tiny_reviews.jsonl": FIXTURE_SHA},
        train_size=16,
        validation_size=8,
        test_size=8,
        seed=42,
    )

    manifest = read_manifest(manifest_path, DataManifest)
    assert manifest.split_uris == {
        "train": "gs://private-data/versions/fixture-v1/train.parquet",
        "validation": "gs://private-data/versions/fixture-v1/validation.parquet",
        "test": "gs://private-data/versions/fixture-v1/test.parquet",
    }
    assert {
        "private-data/versions/fixture-v1/train.parquet",
        "private-data/versions/fixture-v1/validation.parquet",
        "private-data/versions/fixture-v1/test.parquet",
        "private-data/versions/fixture-v1/data-manifest.json",
    } <= fake_storage.objects.keys()
