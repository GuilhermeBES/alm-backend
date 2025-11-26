from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.inference import (
    InferenceResultResponse,
    InferenceUploadResponse,
    JobStatus,
    ModelsListResponse,
)
from app.services.inference_service import inference_service

router = APIRouter()


@router.get("/models", response_model=ModelsListResponse)
async def list_models():
    """List all available PyTorch models.

    Returns:
        ModelsListResponse: List of available models with their configurations

    """
    models = inference_service.list_available_models()
    return ModelsListResponse(models=models)


@router.post(
    "/inference/{model_name}",
    response_model=InferenceUploadResponse,
    status_code=202,
)
async def submit_inference(model_name: str, file: Annotated[UploadFile, File()]):
    """Submit CSV file for inference processing.

    The request will be queued and processed asynchronously.
    Returns a job_id that can be used to retrieve results later.

    Args:
        model_name: Name of the model to use (from URL path)
        file: CSV file containing the data to process

    Returns:
        InferenceUploadResponse: Job ID, model name, and status

    Example:
        curl -X POST "http://localhost:8000/api/v1/inference/petr_4_xlstm_embedding_128" \
             -F "file=@data.csv"

    """  # noqa: E501
    try:
        # Validate model exists
        available_models = inference_service.list_available_models()
        model_names = [m.name for m in available_models]

        if model_name not in model_names:
            raise HTTPException(
                status_code=404,
                detail=f"Model '{model_name}' not found. Available models: {model_names}",  # noqa: E501
            )

        # Validate file type
        if not file.filename.endswith(".csv"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Expected CSV file, got: {file.filename}",
            )

        # Read CSV content
        content = await file.read()
        csv_data = content.decode("utf-8")

        # Submit job
        job_id = await inference_service.submit_job(model_name, csv_data)

        return InferenceUploadResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            model=model_name,
            message=f"CSV file '{file.filename}' uploaded and queued for processing. Use job_id to retrieve results.",  # noqa: E501
        )

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Failed to decode CSV file. Ensure the file is UTF-8 encoded.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting job: {e!s}")


@router.get("/result/{job_id}", response_model=InferenceResultResponse)
async def get_inference_result(job_id: str):
    """Get the result of an inference job.

    Args:
        job_id: The unique identifier returned when submitting the job

    Returns:
        InferenceResultResponse: Job status and results (if completed)

    Example:
        curl "http://localhost:8000/api/v1/result/{job_id}"

    """
    try:
        return await inference_service.get_job_result(job_id)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving result: {e!s}",
        )
