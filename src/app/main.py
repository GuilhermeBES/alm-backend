from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import inference, portfolio, auth, forecast
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

# Configurar CORS para permitir requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Frontend dev server (Vite)
        "http://127.0.0.1:5173",
        "http://localhost:3000",  # Frontend dev server (React)
        "http://127.0.0.1:3000",
        "http://192.168.1.19:3000", # Frontend Docker container access
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os métodos (GET, POST, etc)
    allow_headers=["*"],  # Permite todos os headers
)

app.include_router(inference.router, prefix="/api/v1", tags=["inference"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["portfolio"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(forecast.router, prefix="/api/v1", tags=["forecast"])


@app.get("/")
def read_root():
    return {"message": "Welcome to ALM xLSTM Inference Service"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
