"""Tests for health endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root() -> None:
    """Root endpoint returns API metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "AI Idea Researcher API"
    assert data["version"] == "0.2.0"
    assert data["status"] == "running"


def test_health() -> None:
    """Health endpoint returns ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("app.api.routes.health.check_database_connection", return_value=True)
def test_database_health_connected(mock_check) -> None:
    """Database health endpoint returns connected when DB is up."""
    # Need to override get_db since no real DB in unit tests
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.database.database import get_db
    from app.database.base import Base

    # Create in-memory SQLite for test
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/health/database")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
    finally:
        app.dependency_overrides.clear()
