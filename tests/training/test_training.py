from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from reviewsignal.training import (
    ArtifactChecksumError,
    PromotionGateError,
    build_pipeline,
    evaluate_model,
    load_verified_artifact,
    make_model_version,
    save_artifact,
    validate_promotion,
)


def _training_frame() -> pd.DataFrame:
    positives = [
        "excellent reliable product",
        "excellent quality and value",
        "excellent sturdy and comfortable",
        "excellent fantastic purchase",
        "excellent fit and great design",
        "excellent item works beautifully",
    ]
    negatives = [
        "terrible unreliable product",
        "terrible quality and waste",
        "terrible flimsy and uncomfortable",
        "terrible defective purchase",
        "terrible fit and bad design",
        "terrible item works horribly",
    ]
    return pd.DataFrame(
        {
            "text": positives + negatives,
            "label": [1] * len(positives) + [0] * len(negatives),
        }
    )


def test_pipeline_uses_the_pinned_model_parameters() -> None:
    pipeline = build_pipeline()
    params = pipeline.get_params()

    assert params["tfidf__ngram_range"] == (1, 2)
    assert params["tfidf__max_features"] == 50_000
    assert params["tfidf__min_df"] == 2
    assert params["tfidf__sublinear_tf"] is True
    assert params["classifier__C"] == 1.0
    assert params["classifier__max_iter"] == 1000
    assert params["classifier__random_state"] == 42


def test_evaluation_reports_required_metrics_and_dummy_comparison() -> None:
    frame = _training_frame()
    model = build_pipeline().fit(frame["text"], frame["label"])

    report = evaluate_model(
        model,
        frame,
        training_labels=frame["label"],
        latency_repetitions=3,
    )

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
    } <= report.keys()
    assert report["confusion_matrix"] == [[6, 0], [0, 6]]
    assert report["macro_f1"] > report["dummy_macro_f1"]
    assert report["inference_latency_ms"] >= 0


def test_artifact_round_trip_requires_the_expected_checksum(tmp_path) -> None:
    frame = _training_frame()
    model = build_pipeline().fit(frame["text"], frame["label"])
    artifact_path = tmp_path / "model.joblib"

    checksum = save_artifact(model, artifact_path)

    restored = load_verified_artifact(artifact_path, checksum)
    assert restored.predict(["excellent quality"])[0] == 1
    with pytest.raises(ArtifactChecksumError):
        load_verified_artifact(artifact_path, "0" * 64)


@pytest.mark.parametrize(
    ("candidate", "dummy", "production", "expected_message"),
    [
        (0.84, 0.50, None, "0.85"),
        (0.85, 0.71, None, "0.15"),
        (0.88, 0.50, 0.90, "regresses"),
        (float("nan"), 0.50, None, "finite"),
        (0.90, float("inf"), None, "finite"),
        (0.90, 0.50, -0.01, "between 0 and 1"),
    ],
)
def test_promotion_gate_blocks_weak_or_regressing_candidates(
    candidate: float,
    dummy: float,
    production: float | None,
    expected_message: str,
) -> None:
    with pytest.raises(PromotionGateError, match=expected_message):
        validate_promotion(candidate, dummy, production)


def test_promotion_gate_accepts_qualified_candidates() -> None:
    validate_promotion(0.90, 0.50)
    validate_promotion(0.895, 0.50, production_macro_f1=0.90)


def test_model_version_uses_utc_timestamp_and_short_git_sha() -> None:
    timestamp = datetime(2026, 8, 7, 12, 34, 56, tzinfo=UTC)

    assert make_model_version("abcdef123456", timestamp) == "20260807T123456Z-abcdef1"
