import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import get_current_user
from app.models.user import User


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "test@example.com"
    user.is_active = True
    return user


@pytest.fixture
def client(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_hermes_health_endpoint(client):
    response = client.get("/api/v1/hermes/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@patch('app.hermes.gateway.run_exam_skill', new_callable=AsyncMock)
def test_extract_exam_endpoint(mock_run_exam_skill, client):
    mock_run_exam_skill.return_value = {"success": True, "questions": []}
    response = client.post("/api/v1/hermes/exam/extract", json={
        "file_path": "/path/to/test.pdf"
    })
    assert response.status_code == 200
    assert response.json()["success"] is True


@patch('app.hermes.gateway.run_exam_skill', new_callable=AsyncMock)
def test_upload_exam_endpoint(mock_run_exam_skill, client):
    mock_run_exam_skill.return_value = {"success": True, "questions": []}
    response = client.post(
        "/api/v1/hermes/exam/upload",
        files={"file": ("test.pdf", b"fake pdf content", "application/pdf")}
    )
    assert response.status_code == 200
    assert response.json()["success"] is True