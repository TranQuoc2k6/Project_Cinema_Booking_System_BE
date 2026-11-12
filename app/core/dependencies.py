"""
Dependency xác thực & phân quyền dùng chung cho toàn bộ API.

Cách dùng ở router:
    from app.core.dependencies import get_current_user, require_admin

    @router.get("/me")
    def me(current_user: User = Depends(get_current_user)): ...

    @router.post("/movies", dependencies=[Depends(require_admin)])
    def create_movie(...): ...

Mã lỗi:
    401 -> thiếu token / token sai / token hết hạn / user không còn tồn tại
    403 -> token hợp lệ nhưng tài khoản bị khóa hoặc không đủ quyền
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt      # type: ignore[reportMissingModuleSource]
from jose.exceptions import ExpiredSignatureError       # type: ignore[reportMissingModuleSource]
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from database import get_db

ADMIN_ROLE_NAME = "ADMIN"

# Swagger: bấm "Authorize" rồi dán access_token (không cần gõ chữ "Bearer ").
# auto_error=False để tự trả 401 thống nhất.
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Dán access_token lấy từ POST /api/v1/auth/login",
)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Đọc header `Authorization: Bearer <token>` và trả về User hiện tại."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Chưa đăng nhập hoặc thiếu token")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except ExpiredSignatureError:  # phải bắt trước JWTError vì là lớp con
        raise _unauthorized("Token đã hết hạn, vui lòng đăng nhập lại")
    except JWTError:
        raise _unauthorized("Token không hợp lệ")

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise _unauthorized("Token không hợp lệ")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _unauthorized("Token không hợp lệ")  # user đã bị xóa

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị khóa",
        )
    return user

# Phân quyền ADMIN. Role đọc từ DB (không tin claim trong token).
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Chỉ cho phép role ADMIN. Role đọc từ DB (không tin claim trong token)."""
    role_name = current_user.role.name if current_user.role else ""
    if role_name.upper() != ADMIN_ROLE_NAME:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thực hiện thao tác này (yêu cầu quyền Admin)",
        )
    return current_user
