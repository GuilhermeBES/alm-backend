from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ModelInfo(BaseModel):
    """Information about an available model."""

    name: str
    path: str
    config: dict
    loaded: bool = False


class ModelsListResponse(BaseModel):
    """Response for listing available models."""

    models: list[ModelInfo]


class InferenceRequest(BaseModel):
    """Request to run inference on data - used internally."""

    model: str = Field(..., description="Name of the model to use")
    data: str = Field(..., description="CSV data with headers")


class InferenceUploadResponse(BaseModel):
    """Response after uploading CSV for inference."""

    job_id: str = Field(..., description="Unique identifier for the job")
    status: JobStatus
    model: str = Field(..., description="Model name used for inference")
    message: str


class InferenceResponse(BaseModel):
    """Response after submitting inference request."""

    job_id: str = Field(..., description="Unique identifier for the job")
    status: JobStatus
    message: str


class PredictionResult(BaseModel):
    """Single prediction result."""

    predicted_prices: list[float]
    prediction_horizon: int
    current_price: float


class InferenceResultResponse(BaseModel):
    """Response containing inference results."""

    job_id: str
    status: JobStatus
    submitted_at: datetime
    completed_at: datetime | None = None
    model: str
    result: PredictionResult | None = None
    error: str | None = None
