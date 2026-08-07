from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from reviewsignal.api import create_app


class FakeRuntime:
    ready = True
    readiness_reason = None
    model_version = "20260807T123456Z-abcdef1"

    def predict(self, text: str) -> dict[str, object]:
        probability = 0.94 if "love" in text.casefold() else 0.08
        return {
            "label": "positive" if probability >= 0.5 else "negative",
            "positive_probability": probability,
        }

    def metadata(self) -> dict[str, object]:
        return {
            "model_version": self.model_version,
            "dataset_version": "amazon-polarity-test-s42",
            "trained_at": "2026-08-07T12:34:56Z",
            "metrics": {"macro_f1": 0.91, "accuracy": 0.91},
        }


class UnavailableRuntime:
    ready = False
    readiness_reason = "artifact checksum mismatch"
    model_version = None

    def predict(self, text: str) -> dict[str, object]:
        raise AssertionError("unavailable runtime must not predict")

    def metadata(self) -> dict[str, object]:
        return {"status": "unavailable"}


class BrokenRuntime(FakeRuntime):
    def predict(self, text: str) -> dict[str, object]:
        raise RuntimeError("synthetic failure")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(runtime=FakeRuntime()))


def test_prediction_contract_includes_probability_model_and_request_id(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/predict", json={"text": "I love this product."})

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "label": "positive",
        "positive_probability": 0.94,
        "model_version": "20260807T123456Z-abcdef1",
        "request_id": payload["request_id"],
    }
    uuid.UUID(payload["request_id"])
    assert response.headers["x-request-id"] == payload["request_id"]


@pytest.mark.parametrize("text", ["", "   ", "x" * 5001])
def test_prediction_rejects_blank_or_oversized_text(client: TestClient, text: str) -> None:
    response = client.post("/api/v1/predict", json={"text": text})

    assert response.status_code == 422


def test_submitted_review_text_never_appears_in_logs(caplog) -> None:
    submitted_text = "PRIVATE REVIEW TEXT 9f93f1"
    caplog.set_level(logging.INFO)
    client = TestClient(create_app(runtime=FakeRuntime()))

    response = client.post("/api/v1/predict", json={"text": submitted_text})

    assert response.status_code == 200
    assert submitted_text not in caplog.text
    assert "request_id=" in caplog.text
    assert "model_version=20260807T123456Z-abcdef1" in caplog.text


def test_health_readiness_metadata_docs_and_page(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {
        "status": "ready",
        "model_version": "20260807T123456Z-abcdef1",
    }
    metadata = client.get("/api/v1/model").json()
    assert metadata["metrics"] == {"macro_f1": 0.91, "accuracy": 0.91}
    assert "artifact_uri" not in metadata
    assert client.get("/docs").status_code == 200

    page = client.get("/")
    assert page.status_code == 200
    assert 'id="review-text"' in page.text
    assert 'aria-live="polite"' in page.text
    assert "Methodology" in page.text
    assert "Limitations" in page.text
    assert "Demonstration only" in page.text


def test_unavailable_model_fails_readiness_and_prediction() -> None:
    client = TestClient(create_app(runtime=UnavailableRuntime()))

    readiness = client.get("/readyz")
    prediction = client.post("/api/v1/predict", json={"text": "valid review"})

    assert readiness.status_code == 503
    assert readiness.json() == {
        "status": "unavailable",
        "reason": "artifact checksum mismatch",
    }
    assert prediction.status_code == 503
    assert prediction.json()["detail"] == "model unavailable"


def test_unexpected_prediction_error_returns_safe_response(caplog) -> None:
    caplog.set_level(logging.ERROR)
    client = TestClient(create_app(runtime=BrokenRuntime()), raise_server_exceptions=False)

    response = client.post("/api/v1/predict", json={"text": "do not echo this"})

    assert response.status_code == 500
    assert response.json()["detail"] == "internal server error"
    assert "do not echo this" not in caplog.text
    assert "synthetic failure" not in response.text
