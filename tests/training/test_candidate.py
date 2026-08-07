from __future__ import annotations

from datetime import UTC, datetime

from reviewsignal.ingestion import load_jsonl_fixture, materialize_dataset
from reviewsignal.manifests import ModelManifest, read_manifest
from reviewsignal.training import load_verified_artifact, train_candidate


def test_candidate_training_records_metrics_lineage_and_loadable_artifact(
    tmp_path, fixture_path
) -> None:
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

    model_manifest_path = train_candidate(
        data_manifest_path,
        output_dir=tmp_path / "models",
        git_sha="abcdef123456",
        trained_at=datetime(2026, 8, 7, 12, 34, 56, tzinfo=UTC),
        latency_repetitions=2,
    )

    manifest = read_manifest(model_manifest_path, ModelManifest)
    assert manifest.model_version == "20260807T123456Z-abcdef1"
    assert manifest.dataset_version.startswith("synthetic-fixture-")
    assert {"validation", "test", "artifact_size_bytes"} <= manifest.metrics.keys()
    assert {
        "accuracy",
        "macro_f1",
        "precision",
        "recall",
        "roc_auc",
        "confusion_matrix",
        "dummy_macro_f1",
        "macro_f1_improvement",
        "inference_latency_ms",
    } <= manifest.metrics["validation"].keys()
    artifact_path = model_manifest_path.parent / "model.joblib"
    assert manifest.metrics["artifact_size_bytes"] == artifact_path.stat().st_size
    model = load_verified_artifact(artifact_path, manifest.artifact_sha256)
    assert model.predict_proba(["excellent reliable item"]).shape == (1, 2)
