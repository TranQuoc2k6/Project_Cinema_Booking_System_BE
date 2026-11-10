import os
import sys
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Đảm bảo đường dẫn import tới app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.role import Role

client = TestClient(app)


def test_password_hashing():
    """Kiểm tra mã hóa và xác thực mật khẩu"""
    password = "secret_password_123"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_token_creation_and_decoding():
    """Kiểm tra tạo và giải mã JWT token"""
    payload = {
        "user_id": 99,
        "email": "test@cinema.com",
        "role": "admin",
    }
    token = create_access_token(payload)
    assert isinstance(token, str)

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["user_id"] == 99
    assert decoded["email"] == "test@cinema.com"
    assert decoded["role"] == "admin"


def test_require_admin_with_admin_user():
    """Kiểm tra require_admin cho phép tài khoản Admin (role_id=1 hoặc role='ADMIN')"""
    admin_user = User(
        id=1,
        role_id=1,
        full_name="Admin Test",
        email="admin@test.com",
        password_hash="hash",
        is_active=True,
    )
    admin_role = Role(id=1, name="ADMIN")
    admin_user.role = admin_role

    # Phải thành công trả về chính admin_user
    result = require_admin(current_user=admin_user)
    assert result.id == 1
    assert result.email == "admin@test.com"


def test_require_admin_blocks_non_admin_user():
    """Kiểm tra require_admin chặn tài khoản khách hàng thường (HTTP 403 Forbidden)"""
    customer_user = User(
        id=2,
        role_id=2,
        full_name="Customer Test",
        email="customer@test.com",
        password_hash="hash",
        is_active=True,
    )
    customer_role = Role(id=2, name="USER")
    customer_user.role = customer_role

    with pytest.raises(HTTPException) as exc_info:
        require_admin(current_user=customer_user)

    assert exc_info.value.status_code == 403
    assert "Chức năng này chỉ dành riêng cho Quản trị viên" in exc_info.value.detail


def test_admin_api_endpoint_unauthorized_without_token():
    """Kiểm tra gọi API /api/admin/check-admin không có token -> trả về HTTP 401"""
    response = client.get("/api/admin/check-admin")
    assert response.status_code == 401
    assert "Yêu cầu xác thực tài khoản" in response.json()["detail"]


def test_admin_api_endpoint_with_invalid_token():
    """Kiểm tra gọi API /api/admin/check-admin với token sai -> trả về HTTP 401"""
    headers = {"Authorization": "Bearer invalid_token_12345"}
    response = client.get("/api/admin/check-admin", headers=headers)
    assert response.status_code == 401
    assert "Token xác thực không hợp lệ" in response.json()["detail"]


def test_admin_api_endpoint_forbidden_for_normal_user():
    """Kiểm tra gọi API /api/admin/check-admin với token của user thường -> trả về HTTP 403"""
    from app.core.dependencies import get_current_user

    # Mock user thường cho test
    mock_customer = User(
        id=2,
        role_id=2,
        full_name="Customer User",
        email="customer@cinema.com",
        password_hash="hash",
        is_active=True,
    )
    mock_customer.role = Role(id=2, name="USER")

    # Override get_current_user
    app.dependency_overrides[get_current_user] = lambda: mock_customer

    try:
        response = client.get("/api/admin/check-admin")
        assert response.status_code == 403
        assert "Chức năng này chỉ dành riêng cho Quản trị viên" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_admin_api_endpoint_success_for_admin():
    """Kiểm tra gọi API /api/admin/check-admin với tài khoản Admin -> trả về HTTP 200 OK"""
    from app.core.dependencies import get_current_user

    # Mock admin user cho test
    mock_admin = User(
        id=1,
        role_id=1,
        full_name="Le Van Hung Admin",
        email="admin@cinema.com",
        password_hash="hash",
        is_active=True,
    )
    mock_admin.role = Role(id=1, name="ADMIN")

    app.dependency_overrides[get_current_user] = lambda: mock_admin

    try:
        response = client.get("/api/admin/check-admin")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["admin"]["email"] == "admin@cinema.com"
        assert data["admin"]["role"] == "admin"
    finally:
        app.dependency_overrides.clear()
