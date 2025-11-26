import asyncio
import contextlib
import io
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from app.schemas.inference import (
    InferenceResultResponse,
    JobStatus,
    ModelInfo,
    PredictionResult,
)


class InferenceJob:
    """Represents a single inference job."""

    def __init__(self, job_id: str, model: str, data: str) -> None:
        self.job_id = job_id
        self.model = model
        self.data = data
        self.status = JobStatus.PENDING
        self.submitted_at = datetime.utcnow()
        self.completed_at: datetime | None = None
        self.result: PredictionResult | None = None
        self.error: str | None = None


class InferenceService:
    """Service for managing inference operations."""

    def __init__(self, models_dir: str = "models") -> None:
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)

        # In-memory job storage (use Redis/DB in production)
        self.jobs: dict[str, InferenceJob] = {}

        # Queue for pending jobs
        self.job_queue: asyncio.Queue = asyncio.Queue()

        # Loaded models cache
        self.loaded_models: dict[str, tuple] = {}

        # Device configuration
        self.device = self._get_device()

        # Start background worker
        self.worker_task: asyncio.Task | None = None

    def _get_device(self) -> torch.device:
        """Get the best available device."""
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    async def start_worker(self) -> None:
        """Start the background worker."""
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._process_queue())

    async def stop_worker(self) -> None:
        """Stop the background worker."""
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.worker_task

    def list_available_models(self) -> list[ModelInfo]:
        """List all available models in the models directory."""
        models = []
        for model_path in self.models_dir.glob("*.pt"):
            try:
                # Load checkpoint to get config
                checkpoint = torch.load(model_path, map_location="cpu")
                config = checkpoint.get("config", {})

                model_info = ModelInfo(
                    name=model_path.stem,
                    path=str(model_path),
                    config=config,
                    loaded=model_path.stem in self.loaded_models,
                )
                models.append(model_info)
            except Exception as e:
                print(f"Error loading model info for {model_path}: {e}")

        return models

    def _load_model(self, model_name: str):
        """Load a model from disk."""
        if model_name in self.loaded_models:
            return self.loaded_models[model_name]

        model_path = self.models_dir / f"{model_name}.pt"
        if not model_path.exists():
            msg = f"Model not found: {model_name}"
            raise FileNotFoundError(msg)

        # Import xLSTM from submodule
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "PyxLSTM"))
        from xLSTM.model import xLSTM

        # Load checkpoint
        checkpoint = torch.load(model_path, map_location=self.device)
        config = checkpoint["config"]

        # Create model
        model = xLSTM(
            input_size=config["input_size"],
            hidden_size=config["hidden_size"],
            num_layers=config["num_layers"],
            num_blocks=config["num_blocks"],
            output_size=config["output_size"],
            dropout=config["dropout"],
            lstm_type="alternate",
            use_projection=True,
        ).to(self.device)

        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

        self.loaded_models[model_name] = (model, config)
        return model, config

    def _parse_csv_data(self, csv_data: str) -> tuple:
        """Parse CSV data into embeddings and prices."""
        df = pd.read_csv(io.StringIO(csv_data))

        embeddings = []
        prices = []

        # Extract embedding columns
        emb_cols = [f"emb_{i}" for i in range(128)]

        for _, row in df.iterrows():
            emb_vec = [row[col] for col in emb_cols if col in df.columns]

            if len(emb_vec) == 128:
                embeddings.append(emb_vec)
                prices.append(row["last_price"])

        return np.array(embeddings, dtype=np.float32), np.array(
            prices,
            dtype=np.float32,
        )

    def _run_inference(
        self,
        model,
        config,
        embeddings: np.ndarray,
        prices: np.ndarray,
    ) -> PredictionResult:
        """Run inference on the provided data."""
        prediction_horizon = config.get("prediction_horizon", 1)

        # Use the last sequence for prediction
        # Assuming we need at least seq_length points
        seq_length = 20  # Default from training

        if len(embeddings) < seq_length:
            msg = f"Not enough data points. Need at least {seq_length}, got {len(embeddings)}"  # noqa: E501
            raise ValueError(
                msg,
            )

        # Take the last seq_length embeddings
        sequence = embeddings[-seq_length:]
        current_price = prices[-1]

        # Convert to tensor
        seq_tensor = (
            torch.FloatTensor(sequence).unsqueeze(0).to(self.device)
        )  # (1, seq_length, 128)

        # Run inference
        with torch.no_grad():
            predictions, _ = model.predict_last(seq_tensor)

        # predictions shape: (1, prediction_horizon)
        pred_relatives = predictions[0].cpu().numpy()

        # Convert relative changes to actual prices
        predicted_prices = [
            float(current_price * (1.0 + rel)) for rel in pred_relatives
        ]

        return PredictionResult(
            predicted_prices=predicted_prices,
            prediction_horizon=prediction_horizon,
            current_price=float(current_price),
        )

    async def submit_job(self, model: str, data: str) -> str:
        """Submit a new inference job."""
        job_id = str(uuid.uuid4())
        job = InferenceJob(job_id=job_id, model=model, data=data)

        self.jobs[job_id] = job
        await self.job_queue.put(job)

        return job_id

    async def get_job_result(self, job_id: str) -> InferenceResultResponse:
        """Get the result of a job."""
        if job_id not in self.jobs:
            msg = f"Job not found: {job_id}"
            raise ValueError(msg)

        job = self.jobs[job_id]

        return InferenceResultResponse(
            job_id=job.job_id,
            status=job.status,
            submitted_at=job.submitted_at,
            completed_at=job.completed_at,
            model=job.model,
            result=job.result,
            error=job.error,
        )

    async def _process_queue(self) -> None:
        """Background worker to process jobs from the queue."""
        while True:
            try:
                job = await self.job_queue.get()

                # Update status
                job.status = JobStatus.PROCESSING

                try:
                    # Load model
                    model, config = self._load_model(job.model)

                    # Parse data
                    embeddings, prices = self._parse_csv_data(job.data)

                    # Run inference
                    result = self._run_inference(model, config, embeddings, prices)

                    # Update job
                    job.result = result
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.utcnow()

                except Exception as e:
                    job.error = str(e)
                    job.status = JobStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    print(f"Error processing job {job.job_id}: {e}")

                finally:
                    self.job_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Unexpected error in worker: {e}")
                await asyncio.sleep(1)


# Global instance
inference_service = InferenceService()
