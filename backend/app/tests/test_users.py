from fastapi.testclient import TestClient
from app.main import app
import pytest

client = TestClient(app)

def test_create_user():
    response = client.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpass",
            "full_name": "Test User"
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data

def test_read_users():
    response = client.get("/api/v1/users/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_read_user():
    # 首先创建用户
    create_response = client.post(
        "/api/v1/users/",
        json={
            "email": "test2@example.com",
            "username": "testuser2",
            "password": "testpass",
            "full_name": "Test User 2"
        },
    )
    user_id = create_response.json()["id"]
    
    # 然后读取该用户
    response = client.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
