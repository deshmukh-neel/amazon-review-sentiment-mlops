from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from google.api_core.exceptions import GoogleAPICallError

from reviewsignal.manifests import ModelManifest, read_manifest
from reviewsignal.storage import StorageUriError, download_uri
from reviewsignal.training import ArtifactChecksumError, load_verified_artifact


class RuntimeLoadError(RuntimeError):
    """Raised when the pinned production model cannot be loaded safely."""


class ModelRuntime:
    def __init__(self, model: Any, manifest: ModelManifest) -> None:
        self._model = model
        self._manifest = manifest
        self.ready = True
        self.readiness_reason: str | None = None
        self.model_version = manifest.model_version

    @classmethod
    def from_manifest(
        cls,
        manifest_uri: str | Path,
        *,
        storage_client: Any | None = None,
    ) -> ModelRuntime:
        try:
            with tempfile.TemporaryDirectory(prefix="reviewsignal-model-") as temp_dir:
                staging_dir = Path(temp_dir)
                manifest_path = download_uri(
                    str(manifest_uri),
                    staging_dir / "model-manifest.json",
                    client=storage_client,
                )
                manifest = read_manifest(manifest_path, ModelManifest)
                artifact_path = download_uri(
                    manifest.artifact_uri,
                    staging_dir / "model.joblib",
                    client=storage_client,
                )
                model = load_verified_artifact(artifact_path, manifest.artifact_sha256)
        except (
            ArtifactChecksumError,
            GoogleAPICallError,
            KeyError,
            OSError,
            StorageUriError,
            ValueError,
        ) as error:
            raise RuntimeLoadError(f"model artifact checksum or load failure: {error}") from error
        return cls(model, manifest)

    @classmethod
    def from_environment(cls) -> ModelRuntime:
        manifest_uri = os.getenv("MODEL_MANIFEST_URI") or os.getenv("MODEL_MANIFEST_PATH")
        if not manifest_uri:
            raise RuntimeLoadError("MODEL_MANIFEST_URI is not configured")
        return cls.from_manifest(manifest_uri)

    def predict(self, text: str) -> dict[str, object]:
        probability = float(self._model.predict_proba([text])[0, 1])
        return {
            "label": "positive" if probability >= 0.5 else "negative",
            "positive_probability": probability,
        }

    def metadata(self) -> dict[str, object]:
        test_metrics = self._manifest.metrics.get("test", {})
        headline_metrics = {
            name: test_metrics[name]
            for name in ("accuracy", "macro_f1", "roc_auc")
            if name in test_metrics
        }
        return {
            "model_version": self._manifest.model_version,
            "dataset_version": self._manifest.dataset_version,
            "git_sha": self._manifest.git_sha,
            "trained_at": self._manifest.trained_at.isoformat().replace("+00:00", "Z"),
            "metrics": headline_metrics,
        }
