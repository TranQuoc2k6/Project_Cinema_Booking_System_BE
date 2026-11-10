from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from app.models.user import User
from app.models.role import Role
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserResponse
from app.core.security import verify_password, create_access_token
from app.core.dependencies import get_current_user

router = APIRouter(tags=["Xác thực người dùng (Auth)"])


@router.post("/login", response_model=Token, summary="Đăng nhập hệ thống (Lấy JWT Access Token)")
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Xác thực thông tin đăng nhập email và password.
    - Trả về JWT Access Token kèm thông tin người dùng và vai trò (role).
    - Dùng để lưu trữ vào localStorage phía Frontend cho Route Guard và gửi kèm các request sau.
    """
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này hiện đang bị khóa.",
        )

    # Xác định chuỗi role chuẩn
    role_name = "customer"
    if user.role_id == 1 or (user.role and user.role.name.upper() == "ADMIN"):
        role_name = "admin"

    # Tạo JWT token
    token_payload = {
        "user_id": user.id,
        "sub": str(user.id),
        "email": user.email,
        "role": role_name,
        "full_name": user.full_name,
    }
    access_token = create_access_token(data=token_payload)

    # Chuẩn bị phản hồi User
    user_response = UserResponse.model_validate(user)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user_response,
    )


@router.get("/me", response_model=UserResponse, summary="Lấy thông tin người dùng hiện tại")
def get_me(current_user: User = Depends(get_current_user)):
    """
    Lấy thông tin tài khoản đang đăng nhập từ JWT Token.
    """
    return current_user
