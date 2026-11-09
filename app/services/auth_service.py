from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models import User, Role
from app.schemas.auth import RegisterRequest, LoginRequest, Token
from app.schemas.user import UserResponse
from app.core.security import hash_password, verify_password, create_access_token


def register_new_user(db: Session, request: RegisterRequest) -> UserResponse:
    # 1. Kiểm tra Email đã tồn tại chưa (Chặn trùng email)
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được sử dụng. Vui lòng chọn email khác!"
        )

    # 2. Lấy role_id mặc định của CUSTOMER (id = 2)
    customer_role = db.query(Role).filter(Role.name == "USER").first()
    role_id = customer_role.id if customer_role else 2

    # 3. Mã hóa mật khẩu & tạo người dùng mới
    new_user = User(
        full_name=request.full_name,
        email=request.email,
        phone=request.phone,
        password_hash=hash_password(request.password),
        role_id=role_id,
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def authenticate_user(db: Session, request: LoginRequest) -> Token:
    # 1. Tìm người dùng theo Email
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác!",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Kiểm tra mật khẩu
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác!",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Kiểm tra trạng thái hoạt động tài khoản
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản của bạn đã bị khóa!"
        )

    # 4. Sinh JWT Token trả về cho Client
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.name if user.role else "USER"
    }
    access_token = create_access_token(data=token_data)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )