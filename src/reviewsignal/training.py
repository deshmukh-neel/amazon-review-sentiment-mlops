from __future__ import annotations

import hashlib
import importlib.metadata
import math
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

from reviewsignal.data import sha256_file
from reviewsignal.manifests import DataManifest, ModelManifest, read_manifest, write_manifest
from reviewsignal.storage import download_uri, upload_file


class ArtifactChecksumError(RuntimeError):
    """Raised when an artifact does not match its pinned digest."""


class PromotionGateError(RuntimeError):
    """Raised when a candidate is not safe to promote."""


class SplitChecksumError(RuntimeError):
    """Raised when materialized training data no longer matches its manifest."""


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    max_features=50_000,
                    min_df=2,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(C=1.0, max_iter=1000, random_state=42),
            ),
        ]
    )


def evaluate_model(
    model: Pipeline,
    frame: pd.DataFrame,
    *,
    training_labels: pd.Series,
    latency_repetitions: int = 25,
) -> dict[str, Any]:
    labels = frame["label"].to_numpy()
    predictions = model.predict(frame["text"])
    probabilities = model.predict_proba(frame["text"])[:, 1]

    dummy = DummyClassifier(strategy="most_frequent")
    dummy_features = np.zeros((len(training_labels), 1))
    dummy.fit(dummy_features, training_labels)
    dummy_predictions = dummy.predict(np.zeros((len(frame), 1)))
    dummy_macro_f1 = f1_score(labels, dummy_predictions, average="macro")

    sample = [str(frame.iloc[0]["text"])]
    started = time.perf_counter_ns()
    for _ in range(latency_repetitions):
        model.predict_proba(sample)
    latency_ms = (time.perf_counter_ns() - started) / latency_repetitions / 1_000_000

    macro_f1 = f1_score(labels, predictions, average="macro")
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro_f1": float(macro_f1),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "confusion_matrix": confusion_matrix(labels, predictions, labels=[0, 1]).tolist(),
        "dummy_macro_f1": float(dummy_macro_f1),
        "macro_f1_improvement": float(macro_f1 - dummy_macro_f1),
        "inference_latency_ms": latency_ms,
    }


def validate_promotion(
    candidate_macro_f1: float,
    dummy_macro_f1: float,
    production_macro_f1: float | None = None,
) -> None:
    scores = {
        "candidate": candidate_macro_f1,
        "dummy": dummy_macro_f1,
    }
    if production_macro_f1 is not None:
        scores["production"] = production_macro_f1
    for name, score in scores.items():
        if not math.isfinite(score):
            raise PromotionGateError(f"{name} macro-F1 must be finite")
        if not 0 <= score <= 1:
            raise PromotionGateError(f"{name} macro-F1 must be between 0 and 1")
    if candidate_macro_f1 < 0.85:
        raise PromotionGateError("candidate macro-F1 is below the 0.85 minimum")
    if candidate_macro_f1 - dummy_macro_f1 < 0.15:
        raise PromotionGateError("candidate improves on the dummy baseline by less than 0.15")
    if production_macro_f1 is not None and candidate_macro_f1 < production_macro_f1 - 0.01:
        raise PromotionGateError("candidate regresses more than 0.01 from production")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_artifact(model: Pipeline, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, destination, compress=3)
    return _sha256(destination)


def load_verified_artifact(path: Path, expected_sha256: str) -> Pipeline:
    actual_sha256 = _sha256(path)
    if actual_sha256 != expected_sha256:
        raise ArtifactChecksumError(
            f"artifact checksum mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    model = joblib.load(path)
    if not isinstance(model, Pipeline):
        raise ArtifactChecksumError("artifact does not contain a scikit-learn Pipeline")
    return model


def make_model_version(git_sha: str, timestamp: datetime | None = None) -> str:
    if len(git_sha) < 7:
        raise ValueError("git SHA must contain at least seven characters")
    timestamp = timestamp or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    utc_timestamp = timestamp.astimezone(UTC)
    return f"{utc_timestamp:%Y%m%dT%H%M%SZ}-{git_sha[:7].lower()}"


def train_candidate(
    data_manifest_path: Path,
    *,
    output_dir: Path,
    publish_prefix: str | None = None,
    storage_client: Any | None = None,
    git_sha: str,
    trained_at: datetime | None = None,
    latency_repetitions: int = 25,
) -> Path:
    data_manifest = read_manifest(data_manifest_path, DataManifest)
    with tempfile.TemporaryDirectory(prefix="reviewsignal-data-") as temp_dir:
        staging_dir = Path(temp_dir)
        splits: dict[str, pd.DataFrame] = {}
        for name, uri in data_manifest.split_uris.items():
            split_path = download_uri(
                uri,
                staging_dir / f"{name}.parquet",
                client=storage_client,
            )
            actual_checksum = sha256_file(split_path)
            expected_checksum = data_manifest.split_checksums[name]
            if actual_checksum != expected_checksum:
                raise SplitChecksumError(
                    f"{name} split checksum mismatch: expected {expected_checksum}, "
                    f"got {actual_checksum}"
                )
            splits[name] = pd.read_parquet(split_path)
    model = build_pipeline()
    model.fit(splits["train"]["text"], splits["train"]["label"])
    metrics = {
        name: evaluate_model(
            model,
            splits[name],
            training_labels=splits["train"]["label"],
            latency_repetitions=latency_repetitions,
        )
        for name in ("validation", "test")
    }

    trained_at = trained_at or datetime.now(UTC)
    model_version = make_model_version(git_sha, trained_at)
    version_dir = output_dir / model_version
    artifact_path = version_dir / "model.joblib"
    artifact_sha256 = save_artifact(model, artifact_path)
    metrics["artifact_size_bytes"] = artifact_path.stat().st_size
    normalized_publish_prefix = publish_prefix.rstrip("/") if publish_prefix else None
    if normalized_publish_prefix:
        version_publish_prefix = f"{normalized_publish_prefix}/{model_version}"
        artifact_uri = f"{version_publish_prefix}/model.joblib"
        upload_file(artifact_path, artifact_uri, client=storage_client)
    else:
        version_publish_prefix = None
        artifact_uri = str(artifact_path.resolve())

    manifest = ModelManifest(
        model_version=model_version,
        dataset_version=data_manifest.dataset_version,
        git_sha=git_sha,
        artifact_uri=artifact_uri,
        artifact_sha256=artifact_sha256,
        library_versions={
            distribution: importlib.metadata.version(distribution)
            for distribution in ("pandas", "scikit-learn", "joblib")
        }
        | {
            "python": (
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            )
        },
        parameters={
            "tfidf__ngram_range": [1, 2],
            "tfidf__max_features": 50_000,
            "tfidf__min_df": 2,
            "tfidf__sublinear_tf": True,
            "classifier__C": 1.0,
            "classifier__max_iter": 1000,
            "classifier__random_state": 42,
        },
        metrics=metrics,
        trained_at=trained_at,
    )
    manifest_path = version_dir / "model-manifest.json"
    write_manifest(manifest, manifest_path)
    if version_publish_prefix:
        upload_file(
            manifest_path,
            f"{version_publish_prefix}/model-manifest.json",
            client=storage_client,
        )
    return manifest_path
