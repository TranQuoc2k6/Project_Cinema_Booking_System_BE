"""
Router quản lý người dùng: Xem, sửa hồ sơ cá nhân và đổi mật khẩu (Task T3C5C51).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.core.security import verify_password, hash_password
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate, ChangePasswordRequest

router = APIRouter(prefix="/api/v1/users", tags=["Users Profile"])


@router.get("/me", response_model=UserResponse, summary="Xem thông tin hồ sơ cá nhân")
def get_my_profile(current_user: User = Depends(get_current_user)):
    """Trả về thông tin chi tiết của người dùng hiện tại."""
    return current_user


@router.put("/me", response_model=UserResponse, summary="Cập nhật hồ sơ cá nhân")
def update_my_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cập nhật các thông tin cơ bản: họ tên, số điện thoại, avatar.
    """
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()

    if payload.phone is not None:
        # Kiểm tra trùng lặp số điện thoại với user khác
        if payload.phone.strip():
            existing_phone = db.query(User).filter(
                User.phone == payload.phone.strip(),
                User.id != current_user.id
            ).first()
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Số điện thoại này đã được sử dụng bởi tài khoản khác"
                )
            current_user.phone = payload.phone.strip()
        else:
            current_user.phone = None

    if payload.avatar is not None:
        current_user.avatar = payload.avatar.strip() if payload.avatar.strip() else None

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password", summary="Đổi mật khẩu tài khoản")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Đổi mật khẩu người dùng:
    - Bắt buộc kiểm tra đúng mật khẩu hiện tại (old_password).
    - Mật khẩu mới không được trùng với mật khẩu cũ.
    """
    # 1. Kiểm tra mật khẩu cũ
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không chính xác"
        )

    # 2. Kiểm tra mật khẩu mới không trùng mật khẩu cũ
    if payload.old_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới không được trùng với mật khẩu hiện tại"
        )

    # 3. Hash mật khẩu mới và lưu vào database
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()

    return {"message": "Đổi mật khẩu thành công. Vui lòng sử dụng mật khẩu mới cho lần đăng nhập tiếp theo."}
