from __future__ import annotations

from datetime import UTC, datetime

import pytest

from reviewsignal.ingestion import load_jsonl_fixture, materialize_dataset
from reviewsignal.runtime import ModelRuntime, RuntimeLoadError
from reviewsignal.training import train_candidate


def _candidate_manifest(tmp_path, fixture_path):
    source_train, source_test = load_jsonl_fixture(fixture_path)
    data_manifest_path = materialize_dataset(
        source_train,
        source_test,
        output_dir=tmp_path / "data",
        source="synthetic-fixture",
        source_revision="fixture-v1",
        source_checksums={"tiny_reviews.jsonl": "f" * 64},
        train_size=16,
        validation_size=8,
        test_size=8,
        seed=42,
        created_at=datetime(2026, 8, 7, 11, 0, tzinfo=UTC),
    )
    return train_candidate(
        data_manifest_path,
        output_dir=tmp_path / "models",
        git_sha="abcdef123456",
        trained_at=datetime(2026, 8, 7, 12, 34, 56, tzinfo=UTC),
        latency_repetitions=2,
    )


def test_runtime_loads_verified_candidate_and_exposes_safe_metadata(tmp_path, fixture_path) -> None:
    manifest_path = _candidate_manifest(tmp_path, fixture_path)

    runtime = ModelRuntime.from_manifest(manifest_path)
    prediction = runtime.predict("excellent quality and great value")

    assert runtime.ready is True
    assert prediction["label"] in {"positive", "negative"}
    assert 0 <= prediction["positive_probability"] <= 1
    metadata = runtime.metadata()
    assert metadata["model_version"] == "20260807T123456Z-abcdef1"
    assert set(metadata["metrics"]) == {"accuracy", "macro_f1", "roc_auc"}
    assert "artifact_uri" not in metadata
    assert "artifact_sha256" not in metadata


def test_runtime_refuses_a_corrupt_artifact(tmp_path, fixture_path) -> None:
    manifest_path = _candidate_manifest(tmp_path, fixture_path)
    artifact_path = manifest_path.parent / "model.joblib"
    artifact_path.write_bytes(artifact_path.read_bytes() + b"corrupt")

    with pytest.raises(RuntimeLoadError, match="checksum"):
        ModelRuntime.from_manifest(manifest_path)
