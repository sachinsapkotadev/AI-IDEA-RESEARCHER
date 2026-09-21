"""Health check response schemas."""

from pydantic import BaseModel


class RootResponse(BaseModel):
    """Response model for the root endpoint."""

    name: str
    version: str
    status: str


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str


class DatabaseHealthResponse(BaseModel):
    """Response model for the database health endpoint."""

    status: str
    database: str
