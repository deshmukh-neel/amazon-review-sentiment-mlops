from __future__ import annotations

from pathlib import Path

import pytest


class FakeBlob:
    def __init__(self, objects: dict[str, bytes], key: str) -> None:
        self._objects = objects
        self._key = key

    def upload_from_filename(self, filename: str) -> None:
        self._objects[self._key] = Path(filename).read_bytes()

    def download_to_filename(self, filename: str) -> None:
        Path(filename).write_bytes(self._objects[self._key])


class FakeBucket:
    def __init__(self, objects: dict[str, bytes], name: str) -> None:
        self._objects = objects
        self._name = name

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(self._objects, f"{self._name}/{name}")


class FakeStorageClient:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def bucket(self, name: str) -> FakeBucket:
        return FakeBucket(self.objects, name)


@pytest.fixture
def fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "tiny_reviews.jsonl"


@pytest.fixture
def fake_storage() -> FakeStorageClient:
    return FakeStorageClient()
