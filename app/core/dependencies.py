from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db
from app.core.security import decode_access_token
from app.models.user import User

# Khai báo schema xác thực HTTP Bearer token
security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    """
    Middleware/Dependency xác thực người dùng qua JWT Bearer Token trong Authorization Header.
    - Trả về đối tượng User nếu token hợp lệ và tài khoản đang hoạt động.
    - Trả về HTTP 401 Unauthorized nếu token thiếu, sai hoặc đã hết hạn.
    - Trả về HTTP 403 Forbidden nếu tài khoản bị khóa (is_active == False).
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu xác thực tài khoản: Vui lòng cung cấp Bearer Token trong Authorization Header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token xác thực không hợp lệ hoặc đã hết hạn.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Payload của Token thiếu thông tin định danh người dùng (user_id).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Định dạng user_id trong token không hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng trong token không tồn tại trên hệ thống.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này đã bị khóa bởi Quản trị viên. Vui lòng liên hệ ban quản trị.",
        )

    return user


def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Middleware/Dependency kiểm tra nghiêm ngặt quyền Quản trị viên (Admin).
    - Chỉ cho phép người dùng có role == 'ADMIN' hoặc role_id == 1 tiếp tục truy cập.
    - Nếu không đạt yêu cầu, chặn truy cập và trả về HTTP 403 Forbidden.
    """
    is_admin = False

    # 1. Kiểm tra qua quan hệ Role model nếu đã load
    if hasattr(current_user, "role") and current_user.role and hasattr(current_user.role, "name"):
        if current_user.role.name.strip().upper() == "ADMIN":
            is_admin = True

    # 2. Kiểm tra qua role_id mặc định (1 là ADMIN)
    if current_user.role_id == 1:
        is_admin = True

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quyền truy cập bị từ chối: Chức năng này chỉ dành riêng cho Quản trị viên (Admin)!",
        )

    return current_user
