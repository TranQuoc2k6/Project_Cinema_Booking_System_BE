from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.schemas.user import UserStatusUpdate
from app.services import user_service


router = APIRouter(
    tags=["Admin: Users & Customers"],
)


@router.get("/users", summary="Admin: Danh sách người dùng / khách hàng (có tìm kiếm & bộ lọc)")
@router.get("/customers", summary="Admin: Danh sách khách hàng (Alias)", include_in_schema=False)
def get_all_users(
    page: int = Query(1, ge=1, description="Số trang hiển thị"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng bản ghi trên mỗi trang"),
    skip: Optional[int] = Query(None, ge=0, description="Hỗ trợ tương thích skip/limit cũ"),
    search: Optional[str] = Query(None, description="Từ khóa tìm kiếm theo họ tên, email hoặc SĐT"),
    role: Optional[str] = Query(None, description="Lọc theo vai trò: all, customer, admin"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: all, active, blocked"),
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách người dùng / khách hàng trong hệ thống phục vụ trang Quản lý Người dùng của Admin:
    - Phân trang (page, limit)
    - Tìm kiếm linh hoạt theo Họ tên, Email, Số điện thoại
    - Lọc theo Vai trò (Khách hàng vs Quản trị viên)
    - Lọc theo Trạng thái (Đang hoạt động vs Bị khóa)
    - Kèm số lượng đơn vé và tổng tiền chi tiêu
    """
    calc_page = page
    if skip is not None and skip > 0:
        calc_page = (skip // limit) + 1

    return user_service.admin_get_users(
        db=db,
        page=calc_page,
        limit=limit,
        search=search,
        role_filter=role,
        status_filter=status
    )


@router.get("/users/{user_id}", summary="Admin: Xem thông tin chi tiết người dùng / khách hàng")
@router.get("/customers/{user_id}", summary="Admin: Xem chi tiết khách hàng (Alias)", include_in_schema=False)
def get_user_detail(user_id: int, db: Session = Depends(get_db)):
    """
    Xem chi tiết hồ sơ người dùng / khách hàng kèm lịch sử các đơn vé gần nhất.
    """
    return user_service.admin_get_user_by_id(db=db, user_id=user_id)


@router.put("/users/{user_id}/status", summary="Khóa hoặc Mở khóa tài khoản người dùng")
@router.patch("/users/{user_id}/status", summary="Khóa hoặc Mở khóa tài khoản (PATCH)", include_in_schema=False)
@router.put("/customers/{user_id}/status", summary="Khóa hoặc Mở khóa tài khoản khách hàng (Alias)", include_in_schema=False)
def toggle_user_status(
    user_id: int,
    is_active: Optional[bool] = Query(None, description="Trạng thái tài khoản (query param)"),
    payload: Optional[UserStatusUpdate] = None,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Chức năng Khoá / Mở tài khoản (cập nhật cờ is_active) để ngăn chặn spam, gian lận đặt vé.
    - Hỗ trợ truyền qua query param: ?is_active=false
    - Hoặc truyền qua JSON body: {"is_active": false}
    - Chặn không cho khóa Super Admin và không cho tự khóa chính mình.
    """
    target_active = is_active
    if target_active is None and payload is not None and payload.is_active is not None:
        target_active = payload.is_active

    if target_active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thiếu tham số 'is_active'. Vui lòng truyền ?is_active=true/false hoặc gửi JSON body."
        )

    return user_service.admin_toggle_user_status(
        db=db,
        user_id=user_id,
        is_active=target_active,
        current_admin_id=current_admin.id
    )
