from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from database import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, Token
from app.schemas.user import UserResponse
from app.models.user import User
from app.services import auth_service
from app.core.dependencies import get_current_user

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """API Đăng ký tài khoản khách hàng mới"""
    return auth_service.register_new_user(db=db, request=request)


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """API Đăng nhập hệ thống trả về JWT Token"""
    return auth_service.authenticate_user(db=db, request=request)


@router.get("/me", response_model=UserResponse, summary="Lấy thông tin người dùng hiện tại")
def get_me(current_user: User = Depends(get_current_user)):
    """
    Lấy thông tin tài khoản đang đăng nhập từ JWT Token.
    """
    return current_user
