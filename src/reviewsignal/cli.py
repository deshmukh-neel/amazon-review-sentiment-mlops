from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from reviewsignal.ingestion import (
    DATASET_ID,
    PINNED_REVISION,
    download_amazon_polarity,
    materialize_dataset,
    materialize_fixture,
    resolve_hugging_face_source,
)
from reviewsignal.manifests import ModelManifest, read_manifest
from reviewsignal.storage import download_uri
from reviewsignal.training import load_verified_artifact, train_candidate, validate_promotion

app = typer.Typer(no_args_is_help=True, help="Reproducible Amazon review sentiment pipeline.")


def _current_git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@app.command()
def ingest(
    output_dir: Annotated[Path, typer.Option()] = Path("data/processed"),
    publish_prefix: Annotated[str | None, typer.Option()] = None,
    fixture: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    train_size: Annotated[int, typer.Option()] = 80_000,
    validation_size: Annotated[int, typer.Option()] = 10_000,
    test_size: Annotated[int, typer.Option()] = 10_000,
    seed: Annotated[int, typer.Option()] = 42,
) -> None:
    """Validate, de-duplicate, balance, and materialize pinned data splits."""
    if fixture:
        manifest_path = materialize_fixture(
            fixture,
            output_dir,
            publish_prefix=publish_prefix,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            seed=seed,
        )
    else:
        revision, checksums = resolve_hugging_face_source(DATASET_ID, PINNED_REVISION)
        source_train, source_test = download_amazon_polarity(revision)
        manifest_path = materialize_dataset(
            source_train,
            source_test,
            output_dir=output_dir,
            publish_prefix=publish_prefix,
            source=DATASET_ID,
            source_revision=revision,
            source_checksums=checksums,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            seed=seed,
        )
    typer.echo(f"Data manifest: {manifest_path}")


@app.command()
def train(
    data_manifest: Annotated[Path, typer.Option(exists=True)] = Path(
        "data/processed/data-manifest.json"
    ),
    output_dir: Annotated[Path, typer.Option()] = Path("artifacts/candidates"),
    publish_prefix: Annotated[str | None, typer.Option()] = None,
    git_sha: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Train an immutable candidate and record its lineage and metrics."""
    manifest_path = train_candidate(
        data_manifest,
        output_dir=output_dir,
        publish_prefix=publish_prefix,
        git_sha=git_sha or _current_git_sha(),
    )
    typer.echo(f"Candidate created: {manifest_path}")


@app.command()
def evaluate(
    model_manifest: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    production_macro_f1: Annotated[float | None, typer.Option()] = None,
) -> None:
    """Verify an artifact and evaluate its explicit promotion gate."""
    manifest = read_manifest(model_manifest, ModelManifest)
    with tempfile.TemporaryDirectory(prefix="reviewsignal-evaluate-") as temp_dir:
        artifact_path = download_uri(
            manifest.artifact_uri,
            Path(temp_dir) / "model.joblib",
        )
        load_verified_artifact(artifact_path, manifest.artifact_sha256)
    validation = manifest.metrics["validation"]
    validate_promotion(
        validation["macro_f1"],
        validation["dummy_macro_f1"],
        production_macro_f1,
    )
    typer.echo(json.dumps(validation, indent=2, sort_keys=True))
    typer.echo("Promotion gate: passed")


@app.command()
def pipeline(
    fixture: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    data_dir: Annotated[Path, typer.Option()] = Path("data/processed"),
    model_dir: Annotated[Path, typer.Option()] = Path("artifacts/candidates"),
    data_publish_prefix: Annotated[str | None, typer.Option()] = None,
    model_publish_prefix: Annotated[str | None, typer.Option()] = None,
    train_size: Annotated[int, typer.Option()] = 80_000,
    validation_size: Annotated[int, typer.Option()] = 10_000,
    test_size: Annotated[int, typer.Option()] = 10_000,
    seed: Annotated[int, typer.Option()] = 42,
    git_sha: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Run ingestion validation and candidate training end to end."""
    if fixture:
        data_manifest_path = materialize_fixture(
            fixture,
            data_dir,
            publish_prefix=data_publish_prefix,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            seed=seed,
        )
    else:
        revision, checksums = resolve_hugging_face_source(DATASET_ID, PINNED_REVISION)
        source_train, source_test = download_amazon_polarity(revision)
        data_manifest_path = materialize_dataset(
            source_train,
            source_test,
            output_dir=data_dir,
            publish_prefix=data_publish_prefix,
            source=DATASET_ID,
            source_revision=revision,
            source_checksums=checksums,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            seed=seed,
        )
    model_manifest_path = train_candidate(
        data_manifest_path,
        output_dir=model_dir,
        publish_prefix=model_publish_prefix,
        git_sha=git_sha or _current_git_sha(),
    )
    typer.echo(f"Candidate created: {model_manifest_path}")
