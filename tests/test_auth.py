"""
Test T3C5A83: GET /api/v1/auth/me và dependency get_current_user / require_admin.

Chạy (từ thư mục Project_Cinema_Booking_System_BE):
    pip install pytest httpx
    python -m pytest tests/test_auth.py -v
"""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt            # type: ignore[reportMissingModuleSource]
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models import Role, User
from database import Base, get_db
from main import app as fastapi_app

ADMIN_ID, CUSTOMER_ID, LOCKED_ID = 1, 2, 3
ME_URL = "/api/v1/auth/me"
ADMIN_URL = "/api/v1/auth/admin-check"


def _token(user_id, **kwargs) -> str:
    return create_access_token({"sub": str(user_id)}, **kwargs)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionTest = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with SessionTest() as db:
        db.add_all([Role(id=1, name="ADMIN"), Role(id=2, name="USER")])
        db.add_all([
            User(id=ADMIN_ID, role_id=1, full_name="Admin Test", email="admin@test.com",
                 password_hash=hash_password("admin123")),
            User(id=CUSTOMER_ID, role_id=2, full_name="Customer Test", email="customer@test.com",
                 password_hash=hash_password("user123")),
            User(id=LOCKED_ID, role_id=2, full_name="Locked Test", email="locked@test.com",
                 password_hash=hash_password("user123"), is_active=False),
        ])
        db.commit()

    def override_get_db():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


# ----------------------------- GET /auth/me -----------------------------

def test_me_valid_token_returns_profile(client):
    r = client.get(ME_URL, headers=_bearer(_token(CUSTOMER_ID)))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == CUSTOMER_ID
    assert body["email"] == "customer@test.com"
    assert body["role"]["name"] == "USER"
    assert "password_hash" not in body and "password" not in body


def test_me_without_token_returns_401(client):
    r = client.get(ME_URL)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_me_wrong_auth_scheme_returns_401(client):
    r = client.get(ME_URL, headers={"Authorization": f"Basic {_token(CUSTOMER_ID)}"})
    assert r.status_code == 401


def test_me_garbage_token_returns_401(client):
    r = client.get(ME_URL, headers=_bearer("abc.def.ghi"))
    assert r.status_code == 401
    assert r.json()["detail"] == "Token không hợp lệ"


def test_me_expired_token_returns_401(client):
    expired = _token(CUSTOMER_ID, expires_delta=timedelta(seconds=-60))
    r = client.get(ME_URL, headers=_bearer(expired))
    assert r.status_code == 401
    assert "hết hạn" in r.json()["detail"]


def test_me_wrong_signature_returns_401(client):
    forged = jwt.encode({"sub": str(CUSTOMER_ID)}, "khoa-bi-mat-sai", algorithm=settings.ALGORITHM)
    r = client.get(ME_URL, headers=_bearer(forged))
    assert r.status_code == 401


def test_me_token_without_sub_returns_401(client):
    r = client.get(ME_URL, headers=_bearer(create_access_token({"email": "x@test.com"})))
    assert r.status_code == 401


def test_me_token_with_non_numeric_sub_returns_401(client):
    r = client.get(ME_URL, headers=_bearer(_token("abc")))
    assert r.status_code == 401


def test_me_token_of_nonexistent_user_returns_401(client):
    r = client.get(ME_URL, headers=_bearer(_token(99999)))
    assert r.status_code == 401


def test_me_locked_user_returns_403(client):
    r = client.get(ME_URL, headers=_bearer(_token(LOCKED_ID)))
    assert r.status_code == 403


def test_login_then_me_end_to_end(client):
    login = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    r = client.get(ME_URL, headers=_bearer(token))
    assert r.status_code == 200
    assert r.json()["email"] == "admin@test.com"
    assert r.json()["role"]["name"] == "ADMIN"


# ------------------------ require_admin (admin-check) ------------------------

def test_admin_check_without_token_returns_401(client):
    assert client.get(ADMIN_URL).status_code == 401


def test_admin_check_invalid_token_returns_401(client):
    assert client.get(ADMIN_URL, headers=_bearer("abc.def.ghi")).status_code == 401


def test_admin_check_expired_admin_token_returns_401_not_403(client):
    expired = _token(ADMIN_ID, expires_delta=timedelta(seconds=-60))
    assert client.get(ADMIN_URL, headers=_bearer(expired)).status_code == 401


def test_admin_check_customer_returns_403(client):
    r = client.get(ADMIN_URL, headers=_bearer(_token(CUSTOMER_ID)))
    assert r.status_code == 403
    assert "Admin" in r.json()["detail"]


def test_admin_check_admin_returns_200(client):
    r = client.get(ADMIN_URL, headers=_bearer(_token(ADMIN_ID)))
    assert r.status_code == 200
    assert r.json()["role"] == "ADMIN"


def test_admin_check_ignores_role_claim_in_token(client):
    """Customer tự gắn role=ADMIN vào payload (token vẫn ký đúng) cũng phải bị 403."""
    token = create_access_token({"sub": str(CUSTOMER_ID), "role": "ADMIN"})
    assert client.get(ADMIN_URL, headers=_bearer(token)).status_code == 403
