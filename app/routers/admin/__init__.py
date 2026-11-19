"""
Admin Portal Router Package
Gộp và cấu trúc hóa các sub-router quản trị theo từng nghiệp vụ:
- Dashboard (Thống kê KPI, doanh thu, lấp đầy)
- Users & Customers (Quản lý khách hàng, phân quyền, khóa tài khoản)
- Movies (Quản lý phim, thể loại, upload poster, ngừng chiếu)
- Bookings (Quản lý đơn vé, hủy vé & giải phóng ghế)
- Showtimes (Quản lý suất chiếu, chặn trùng giờ chiếu)
"""

from fastapi import APIRouter, Depends
from app.core.dependencies import require_admin
from app.models.user import User

from .dashboard import router as dashboard_router
from .users import router as users_router
from .movies import router as movies_router
from .bookings import router as bookings_router
from .showtimes import router as showtimes_router

# Master Router dành cho toàn bộ module Admin
router = APIRouter(
    dependencies=[Depends(require_admin)],  # Toàn bộ router này được bảo vệ bởi require_admin
)

# Gắn kết các sub-router nghiệp vụ
router.include_router(dashboard_router)
router.include_router(users_router)
router.include_router(movies_router)
router.include_router(bookings_router)
router.include_router(showtimes_router)


@router.get("/check-admin", summary="Kiểm tra xác thực quyền Quản trị viên (Admin Guard)", include_in_schema=False)
def check_admin(admin_user: User = Depends(require_admin)):
    """
    Endpoint kiểm tra token và xác thực quyền Quản trị viên.
    - Trả về HTTP 200 OK nếu hợp lệ kèm thông tin admin.
    - Trả về HTTP 401 nếu thiếu/hỏng token.
    - Trả về HTTP 403 nếu tài khoản không mang quyền ADMIN.
    """
    return {
        "status": "success",
        "message": "Xác thực quyền Quản trị viên (Admin) thành công!",
        "admin": {
            "id": admin_user.id,
            "full_name": admin_user.full_name,
            "email": admin_user.email,
            "role": "admin",
            "role_id": admin_user.role_id,
            "avatar": admin_user.avatar,
        }
    }


__all__ = [
    "router",
    "dashboard_router",
    "users_router",
    "movies_router",
    "bookings_router",
    "showtimes_router",
]
