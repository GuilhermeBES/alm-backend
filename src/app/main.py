from fastapi import FastAPI
from .database import engine, Base
from .routers import items

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ALM - XLSTM - Service")

app.include_router(items.router, prefix="/items", tags=["items"])


@app.get("/")
def read_root():
    return {"message": "Welcome to FastAPI with PostgreSQL"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
