from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from database import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, Token
from app.schemas.user import UserResponse
from app.models.user import User
from app.services import auth_service
from app.core.dependencies import get_current_user, require_admin
from app.models.user import User

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

_RESP_401 = {401: {"description": "Thiếu token, token sai hoặc hết hạn"}}
_RESP_403 = {403: {"description": "Tài khoản bị khóa hoặc không đủ quyền"}}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """API Đăng ký tài khoản khách hàng mới"""
    return auth_service.register_new_user(db=db, request=request)


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """API Đăng nhập hệ thống trả về JWT Token"""
    return auth_service.authenticate_user(db=db, request=request)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Lấy thông tin người dùng hiện tại",
    responses={**_RESP_401, **_RESP_403},
)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Trả về thông tin người dùng đang đăng nhập (theo JWT trong header Authorization).
    - 401: thiếu token / token sai / token hết hạn.
    - 403: tài khoản đã bị khóa.
    """
    return current_user


@router.get(
    "/admin-check",
    summary="Kiểm tra quyền Admin (dùng để test phân quyền)",
    responses={**_RESP_401, **_RESP_403},
)
def admin_check(admin: User = Depends(require_admin)):
    """
    Endpoint mẫu dùng dependency `require_admin`.
    - 200: người gọi là ADMIN.
    - 401: thiếu token / token sai / token hết hạn.
    - 403: đăng nhập hợp lệ nhưng không phải ADMIN.
    """
    return {
        "message": "Bạn có quyền Admin",
        "user_id": admin.id,
        "email": admin.email,
        "role": admin.role.name,
    }
