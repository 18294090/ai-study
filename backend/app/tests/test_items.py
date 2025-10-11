from fastapi.testclient import TestClient
from app.main import app
import pytest

client = TestClient(app)

def test_create_item():
    # 首先创建用户并登录
    client.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpass",
            "full_name": "Test User"
        },
    )
    login_response = client.post(
        "/api/v1/auth/token",
        data={"username": "testuser", "password": "testpass"}
    )
    token = login_response.json()["access_token"]
    
    # 创建商品
    response = client.post(
        "/api/v1/items/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Item",
            "description": "This is a test item",
            "price": 10.5
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Item"
    assert "id" in data

def test_read_items():
    response = client.get("/api/v1/items/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_read_item():
    # 获取之前创建的商品
    response = client.get("/api/v1/items/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert "title" in data
