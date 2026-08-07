from __future__ import annotations

import json

from typer.testing import CliRunner

from reviewsignal.cli import app
from reviewsignal.manifests import ModelManifest, read_manifest
from reviewsignal.training import load_verified_artifact


def test_synthetic_ingest_train_load_predict_pipeline(tmp_path, fixture_path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "data"
    model_dir = tmp_path / "models"

    result = runner.invoke(
        app,
        [
            "pipeline",
            "--fixture",
            str(fixture_path),
            "--data-dir",
            str(data_dir),
            "--model-dir",
            str(model_dir),
            "--train-size",
            "16",
            "--validation-size",
            "8",
            "--test-size",
            "8",
            "--git-sha",
            "abcdef123456",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest_path = next(model_dir.glob("*/model-manifest.json"))
    manifest = read_manifest(manifest_path, ModelManifest)
    model = load_verified_artifact(manifest_path.parent / "model.joblib", manifest.artifact_sha256)
    probability = model.predict_proba(["excellent product and great quality"])[0, 1]
    assert 0 <= probability <= 1
    assert "candidate created" in result.output.lower()


def test_pipeline_command_publishes_data_and_candidate_to_gcs(
    tmp_path, fixture_path, fake_storage, monkeypatch
) -> None:
    monkeypatch.setattr("reviewsignal.storage.storage.Client", lambda: fake_storage)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "pipeline",
            "--fixture",
            str(fixture_path),
            "--data-dir",
            str(tmp_path / "data"),
            "--model-dir",
            str(tmp_path / "models"),
            "--data-publish-prefix",
            "gs://private-data/versions/test-run",
            "--model-publish-prefix",
            "gs://private-models/candidates",
            "--train-size",
            "16",
            "--validation-size",
            "8",
            "--test-size",
            "8",
            "--git-sha",
            "abcdef123456",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "private-data/versions/test-run/data-manifest.json" in fake_storage.objects
    assert any(key.endswith("/model-manifest.json") for key in fake_storage.objects)


def test_evaluate_command_downloads_a_published_gcs_artifact(
    tmp_path, fixture_path, fake_storage, monkeypatch
) -> None:
    monkeypatch.setattr("reviewsignal.storage.storage.Client", lambda: fake_storage)
    runner = CliRunner()
    model_dir = tmp_path / "models"
    pipeline_result = runner.invoke(
        app,
        [
            "pipeline",
            "--fixture",
            str(fixture_path),
            "--data-dir",
            str(tmp_path / "data"),
            "--model-dir",
            str(model_dir),
            "--model-publish-prefix",
            "gs://private-models/candidates",
            "--train-size",
            "16",
            "--validation-size",
            "8",
            "--test-size",
            "8",
            "--git-sha",
            "abcdef123456",
        ],
    )
    assert pipeline_result.exit_code == 0, pipeline_result.output
    manifest_path = next(model_dir.glob("*/model-manifest.json"))
    manifest_payload = json.loads(manifest_path.read_text())
    manifest_payload["metrics"]["validation"].update(
        {
            "macro_f1": 0.90,
            "dummy_macro_f1": 0.30,
            "macro_f1_improvement": 0.60,
        }
    )
    manifest_path.write_text(json.dumps(manifest_payload))

    evaluate_result = runner.invoke(
        app,
        ["evaluate", "--model-manifest", str(manifest_path)],
    )

    assert evaluate_result.exit_code == 0, evaluate_result.output
    assert "Promotion gate: passed" in evaluate_result.output
