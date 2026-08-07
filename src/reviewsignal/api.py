from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints

from reviewsignal.runtime import ModelRuntime, RuntimeLoadError

logger = logging.getLogger("reviewsignal.api")
STATIC_DIR = Path(__file__).parent / "static"


class RuntimeProtocol(Protocol):
    ready: bool
    readiness_reason: str | None
    model_version: str | None

    def predict(self, text: str) -> dict[str, object]: ...

    def metadata(self) -> dict[str, object]: ...


class UnavailableRuntime:
    ready = False
    model_version = None

    def __init__(self, reason: str) -> None:
        self.readiness_reason = reason

    def predict(self, text: str) -> dict[str, object]:
        raise RuntimeError("model unavailable")

    def metadata(self) -> dict[str, object]:
        return {"status": "unavailable"}


ReviewText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=5000),
]


class PredictionRequest(BaseModel):
    text: ReviewText


class PredictionResponse(BaseModel):
    label: Literal["positive", "negative"]
    positive_probability: float = Field(ge=0, le=1)
    model_version: str
    request_id: str


def _load_default_runtime() -> RuntimeProtocol:
    try:
        return ModelRuntime.from_environment()
    except RuntimeLoadError as error:
        logger.warning("model_runtime_unavailable reason=%s", type(error).__name__)
        return UnavailableRuntime("pinned model could not be loaded")


def create_app(runtime: RuntimeProtocol | None = None) -> FastAPI:
    selected_runtime = runtime or _load_default_runtime()
    application = FastAPI(
        title="ReviewSignal API",
        version="1.0.0",
        description="Privacy-safe binary sentiment inference for English Amazon reviews.",
    )
    application.state.runtime = selected_runtime
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.middleware("http")
    async def privacy_safe_request_log(request: Request, call_next: Any):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "request_complete request_id=%s method=%s path=%s status=%s "
            "duration_ms=%.2f model_version=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            selected_runtime.model_version,
        )
        return response

    @application.exception_handler(Exception)
    async def unhandled_error(request: Request, error: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error("request_failed request_id=%s error_type=%s", request_id, type(error).__name__)
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    @application.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @application.post("/api/v1/predict", response_model=PredictionResponse)
    async def predict(payload: PredictionRequest, request: Request) -> PredictionResponse:
        if not selected_runtime.ready:
            raise HTTPException(status_code=503, detail="model unavailable")
        prediction = selected_runtime.predict(payload.text)
        return PredictionResponse(
            label=prediction["label"],
            positive_probability=prediction["positive_probability"],
            model_version=str(selected_runtime.model_version),
            request_id=request.state.request_id,
        )

    @application.get("/api/v1/model")
    async def model_metadata() -> dict[str, object]:
        return selected_runtime.metadata()

    @application.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/readyz", response_model=None)
    async def readiness() -> JSONResponse | dict[str, str]:
        if not selected_runtime.ready:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "reason": selected_runtime.readiness_reason,
                },
            )
        return {"status": "ready", "model_version": str(selected_runtime.model_version)}

    return application


app = create_app()
