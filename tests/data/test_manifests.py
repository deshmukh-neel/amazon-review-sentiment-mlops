from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from reviewsignal.manifests import DataManifest, ModelManifest, read_manifest, write_manifest

SHA256 = "a" * 64
NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def test_data_manifest_round_trip_preserves_complete_lineage(tmp_path) -> None:
    manifest = DataManifest(
        dataset_version="amazon-polarity-ec149c1-s42",
        source="mteb/amazon_polarity",
        source_revision="ec149c1f00d00d00d00d00d00d00d00d00d00d0",
        source_checksums={"train": SHA256, "test": "b" * 64},
        seed=42,
        split_uris={
            "train": "gs://private-data/train.parquet",
            "validation": "gs://private-data/validation.parquet",
            "test": "gs://private-data/test.parquet",
        },
        row_counts={"train": 80_000, "validation": 10_000, "test": 10_000},
        class_counts={
            "train": {"0": 40_000, "1": 40_000},
            "validation": {"0": 5_000, "1": 5_000},
            "test": {"0": 5_000, "1": 5_000},
        },
        created_at=NOW,
    )

    destination = tmp_path / "data-manifest.json"
    write_manifest(manifest, destination)

    assert read_manifest(destination, DataManifest) == manifest


def test_model_manifest_rejects_malformed_sha256() -> None:
    with pytest.raises(ValidationError):
        ModelManifest(
            model_version="20260807T120000Z-abc1234",
            dataset_version="amazon-polarity-ec149c1-s42",
            git_sha="abc123456789",
            artifact_uri="gs://private-models/model.joblib",
            artifact_sha256="not-a-checksum",
            library_versions={"scikit-learn": "1.9.0"},
            parameters={"classifier__C": 1.0},
            metrics={"validation": {"macro_f1": 0.9}},
            trained_at=NOW,
        )


def test_manifest_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DataManifest(
            dataset_version="version",
            source="source",
            source_revision="revision",
            source_checksums={"train": SHA256},
            seed=42,
            split_uris={"train": "train.parquet"},
            row_counts={"train": 2},
            class_counts={"train": {"0": 1, "1": 1}},
            created_at=NOW,
            secret="must not be accepted",
        )
