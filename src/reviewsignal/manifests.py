from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
ManifestT = TypeVar("ManifestT", bound=BaseModel)


class StrictManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataManifest(StrictManifest):
    dataset_version: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_revision: str = Field(min_length=7)
    source_checksums: dict[str, Sha256]
    seed: int
    split_uris: dict[str, str]
    row_counts: dict[str, int]
    class_counts: dict[str, dict[str, int]]
    created_at: AwareDatetime


class ModelManifest(StrictManifest):
    model_version: str = Field(pattern=r"^\d{8}T\d{6}Z-[a-f0-9]{7}$")
    dataset_version: str = Field(min_length=1)
    git_sha: str = Field(min_length=7)
    artifact_uri: str = Field(min_length=1)
    artifact_sha256: Sha256
    library_versions: dict[str, str]
    parameters: dict[str, Any]
    metrics: dict[str, Any]
    trained_at: AwareDatetime


def write_manifest(manifest: BaseModel, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")


def read_manifest(path: Path, manifest_type: type[ManifestT]) -> ManifestT:
    return manifest_type.model_validate_json(path.read_text(encoding="utf-8"))
