"""HTTP entry point for the local KeyRhythm research application."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


app = FastAPI(title="KeyRhythm API", version="0.1.0")


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report whether the API is available."""
    return HealthResponse(status="ok")
