from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


class DataValidationError(ValueError):
    """Raised when source reviews cannot satisfy the data contract."""


def validate_reviews(frame: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"text", "label"}
    missing = required_columns.difference(frame.columns)
    if missing:
        raise DataValidationError(f"missing required columns: {sorted(missing)}")

    validated = frame.loc[:, ["text", "label"]].copy()
    if (
        validated["text"].isna().any()
        or not validated["text"]
        .map(lambda value: isinstance(value, str) and bool(value.strip()))
        .all()
    ):
        raise DataValidationError("text must contain nonblank strings")
    if validated["label"].isna().any() or not validated["label"].isin({0, 1}).all():
        raise DataValidationError("label must be either 0 or 1")

    validated["text"] = validated["text"].str.strip()
    validated["label"] = validated["label"].astype(int)
    validated["_normalized_text"] = validated["text"].str.casefold()
    return validated.drop_duplicates("_normalized_text", keep="first").reset_index(drop=True)


def _require_even_size(name: str, size: int) -> None:
    if size <= 0 or size % 2:
        raise DataValidationError(f"{name} size must be a positive even integer")


def _shuffle(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    return frame.sample(frac=1, random_state=seed).reset_index(drop=True)


def create_balanced_splits(
    source_train: pd.DataFrame,
    source_test: pd.DataFrame,
    *,
    train_size: int,
    validation_size: int,
    test_size: int,
    seed: int = 42,
) -> dict[str, pd.DataFrame]:
    for split_name, size in {
        "train": train_size,
        "validation": validation_size,
        "test": test_size,
    }.items():
        _require_even_size(split_name, size)

    upstream_train = validate_reviews(source_train)
    upstream_test = validate_reviews(source_test)
    train_parts: list[pd.DataFrame] = []
    validation_parts: list[pd.DataFrame] = []

    train_per_class = train_size // 2
    validation_per_class = validation_size // 2
    for label in (0, 1):
        class_rows = _shuffle(upstream_train[upstream_train["label"] == label], seed + label)
        required = train_per_class + validation_per_class
        if len(class_rows) < required:
            raise DataValidationError(
                f"upstream training class {label} has {len(class_rows)} unique rows; "
                f"{required} required"
            )
        train_parts.append(class_rows.iloc[:train_per_class])
        validation_parts.append(class_rows.iloc[train_per_class:required])

    train = _shuffle(pd.concat(train_parts, ignore_index=True), seed)
    validation = _shuffle(pd.concat(validation_parts, ignore_index=True), seed)
    reserved_text = set(train["_normalized_text"]) | set(validation["_normalized_text"])
    upstream_test = upstream_test[~upstream_test["_normalized_text"].isin(reserved_text)]

    test_parts: list[pd.DataFrame] = []
    test_per_class = test_size // 2
    for label in (0, 1):
        class_rows = _shuffle(upstream_test[upstream_test["label"] == label], seed + label)
        if len(class_rows) < test_per_class:
            raise DataValidationError(
                f"upstream test class {label} has {len(class_rows)} unique isolated rows; "
                f"{test_per_class} required"
            )
        test_parts.append(class_rows.iloc[:test_per_class])
    test = _shuffle(pd.concat(test_parts, ignore_index=True), seed)

    return {
        name: frame.loc[:, ["text", "label"]].reset_index(drop=True)
        for name, frame in {"train": train, "validation": validation, "test": test}.items()
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
