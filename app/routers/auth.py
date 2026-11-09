from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from database import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, Token
from app.schemas.user import UserResponse
from app.services import auth_service

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