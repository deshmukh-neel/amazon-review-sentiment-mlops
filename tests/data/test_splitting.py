from __future__ import annotations

import pandas as pd
import pytest

from reviewsignal.data import DataValidationError, create_balanced_splits, validate_reviews


def _source_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    train_rows = [
        {"text": f"Positive training review {index}", "label": 1} for index in range(16)
    ] + [{"text": f"Negative training review {index}", "label": 0} for index in range(16)]
    test_rows = [{"text": f"Positive test review {index}", "label": 1} for index in range(6)] + [
        {"text": f"Negative test review {index}", "label": 0} for index in range(6)
    ]
    test_rows.append({"text": " Positive training review 0 ", "label": 1})
    return pd.DataFrame(train_rows), pd.DataFrame(test_rows)


def test_balanced_splits_are_deterministic_isolated_and_exact() -> None:
    source_train, source_test = _source_frames()

    first = create_balanced_splits(
        source_train,
        source_test,
        train_size=16,
        validation_size=8,
        test_size=8,
        seed=42,
    )
    second = create_balanced_splits(
        source_train,
        source_test,
        train_size=16,
        validation_size=8,
        test_size=8,
        seed=42,
    )

    assert set(first) == {"train", "validation", "test"}
    for split_name, expected_size in {
        "train": 16,
        "validation": 8,
        "test": 8,
    }.items():
        pd.testing.assert_frame_equal(first[split_name], second[split_name])
        assert len(first[split_name]) == expected_size
        assert first[split_name]["label"].value_counts().to_dict() == {
            0: expected_size // 2,
            1: expected_size // 2,
        }

    normalized = {
        name: set(frame["text"].str.strip().str.casefold()) for name, frame in first.items()
    }
    assert normalized["train"].isdisjoint(normalized["validation"])
    assert normalized["train"].isdisjoint(normalized["test"])
    assert normalized["validation"].isdisjoint(normalized["test"])


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame({"text": ["valid", "   "], "label": [1, 0]}),
        pd.DataFrame({"text": ["valid", "unknown"], "label": [1, 2]}),
        pd.DataFrame({"review": ["missing expected column"], "label": [1]}),
    ],
)
def test_validation_rejects_invalid_source_rows(frame: pd.DataFrame) -> None:
    with pytest.raises(DataValidationError):
        validate_reviews(frame)


def test_split_creation_fails_when_a_class_is_too_small() -> None:
    source_train, source_test = _source_frames()

    with pytest.raises(DataValidationError, match="class 0"):
        create_balanced_splits(
            source_train.iloc[:18],
            source_test,
            train_size=16,
            validation_size=8,
            test_size=8,
            seed=42,
        )
