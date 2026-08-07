from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import load_dataset
from huggingface_hub import HfApi

from reviewsignal.data import create_balanced_splits, sha256_file
from reviewsignal.manifests import DataManifest, write_manifest
from reviewsignal.storage import upload_file

DATASET_ID = "mteb/amazon_polarity"
PINNED_REVISION = "ec149c1"


def _attribute(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def resolve_hugging_face_source(
    repo_id: str = DATASET_ID,
    revision: str = PINNED_REVISION,
    *,
    api: Any | None = None,
) -> tuple[str, dict[str, str]]:
    dataset_info = (api or HfApi()).dataset_info(
        repo_id,
        revision=revision,
        files_metadata=True,
    )
    full_revision = str(dataset_info.sha)
    checksums: dict[str, str] = {}
    for sibling in dataset_info.siblings or []:
        lfs = _attribute(sibling, "lfs")
        checksum = _attribute(lfs, "sha256") if lfs else None
        filename = _attribute(sibling, "rfilename")
        if filename and checksum:
            checksums[str(filename)] = str(checksum)
    if len(full_revision) < 40:
        raise RuntimeError("Hugging Face did not return a complete dataset revision SHA")
    if not checksums:
        raise RuntimeError("Hugging Face did not return source file SHA-256 checksums")
    return full_revision, checksums


def download_amazon_polarity(revision: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_dataset = load_dataset(DATASET_ID, revision=revision, split="train")
    test_dataset = load_dataset(DATASET_ID, revision=revision, split="test")
    return train_dataset.to_pandas(), test_dataset.to_pandas()


def load_jsonl_fixture(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.read_json(path, lines=True)
    if "split" not in frame.columns:
        raise ValueError("fixture must contain a split column")
    train = frame[frame["split"] == "train"].drop(columns="split").reset_index(drop=True)
    test = frame[frame["split"] == "test"].drop(columns="split").reset_index(drop=True)
    if train.empty or test.empty:
        raise ValueError("fixture must contain both train and test rows")
    return train, test


def _dataset_version(source: str, revision: str, seed: int, sizes: dict[str, int]) -> str:
    identity = json.dumps(
        {"source": source, "revision": revision, "seed": seed, "sizes": sizes},
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    source_slug = source.replace("/", "-").lower()
    return f"{source_slug}-{digest}-s{seed}"


def materialize_dataset(
    source_train: pd.DataFrame,
    source_test: pd.DataFrame,
    *,
    output_dir: Path,
    publish_prefix: str | None = None,
    storage_client: Any | None = None,
    source: str,
    source_revision: str,
    source_checksums: dict[str, str],
    train_size: int = 80_000,
    validation_size: int = 10_000,
    test_size: int = 10_000,
    seed: int = 42,
    created_at: datetime | None = None,
) -> Path:
    sizes = {
        "train": train_size,
        "validation": validation_size,
        "test": test_size,
    }
    splits = create_balanced_splits(
        source_train,
        source_test,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        seed=seed,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    split_uris: dict[str, str] = {}
    split_checksums: dict[str, str] = {}
    normalized_publish_prefix = publish_prefix.rstrip("/") if publish_prefix else None
    for name, frame in splits.items():
        destination = output_dir / f"{name}.parquet"
        frame.to_parquet(destination, index=False)
        split_checksums[name] = sha256_file(destination)
        if normalized_publish_prefix:
            remote_uri = f"{normalized_publish_prefix}/{name}.parquet"
            upload_file(destination, remote_uri, client=storage_client)
            split_uris[name] = remote_uri
        else:
            split_uris[name] = str(destination.resolve())

    manifest = DataManifest(
        dataset_version=_dataset_version(source, source_revision, seed, sizes),
        source=source,
        source_revision=source_revision,
        source_checksums=source_checksums,
        seed=seed,
        split_uris=split_uris,
        split_checksums=split_checksums,
        row_counts={name: len(frame) for name, frame in splits.items()},
        class_counts={
            name: {
                str(label): int(count)
                for label, count in frame["label"].value_counts().sort_index().items()
            }
            for name, frame in splits.items()
        },
        created_at=created_at or datetime.now(UTC),
    )
    manifest_path = output_dir / "data-manifest.json"
    write_manifest(manifest, manifest_path)
    if normalized_publish_prefix:
        upload_file(
            manifest_path,
            f"{normalized_publish_prefix}/data-manifest.json",
            client=storage_client,
        )
    return manifest_path


def materialize_fixture(
    fixture_path: Path,
    output_dir: Path,
    *,
    publish_prefix: str | None = None,
    storage_client: Any | None = None,
    train_size: int,
    validation_size: int,
    test_size: int,
    seed: int = 42,
) -> Path:
    source_train, source_test = load_jsonl_fixture(fixture_path)
    return materialize_dataset(
        source_train,
        source_test,
        output_dir=output_dir,
        publish_prefix=publish_prefix,
        storage_client=storage_client,
        source="synthetic-fixture",
        source_revision="fixture-v1",
        source_checksums={fixture_path.name: sha256_file(fixture_path)},
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        seed=seed,
    )
