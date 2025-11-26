from contextlib import asynccontextmanager

from fastapi import FastAPI

from .routers import inference
from .services.inference_service import inference_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    await inference_service.start_worker()
    yield
    # Shutdown
    await inference_service.stop_worker()


app = FastAPI(
    title="ALM - xLSTM - Service",
    description="Asset Liability Management with xLSTM inference",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(inference.router, prefix="/api/v1", tags=["inference"])


@app.get("/")
def read_root():
    return {"message": "Welcome to ALM xLSTM Inference Service"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
