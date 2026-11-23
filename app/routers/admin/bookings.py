from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from app.services import booking_service

router = APIRouter(
    prefix="/bookings",
    tags=["Admin: Bookings"],
)


@router.get("", summary="Admin: Danh sách đơn vé (lọc phim/ngày/trạng thái, tìm theo mã vé/SĐT)")
def admin_get_bookings_list(
    page: int = Query(1, ge=1, description="Số trang hiển thị"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng đơn vé trên mỗi trang"),
    movie_id: Optional[int] = Query(None, description="Lọc theo ID phim"),
    date: Optional[str] = Query(None, description="Lọc theo ngày chiếu hoặc ngày đặt (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: all, confirmed, pending, cancelled"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo Mã vé hoặc Số điện thoại"),
    db: Session = Depends(get_db)
):
    """
    API Quản lý đơn vé toàn diện cho Quản trị viên:
    - Danh sách đơn vé kèm thông tin khách hàng, phim, suất chiếu, rạp, phòng, danh sách ghế.
    - Lọc theo phim (movie_id).
    - Lọc theo ngày (date).
    - Lọc theo trạng thái (status).
    - Tìm kiếm theo mã vé (#BK-...) hoặc số điện thoại khách hàng.
    """
    return booking_service.admin_get_bookings(
        db=db,
        page=page,
        limit=limit,
        movie_id=movie_id,
        date_str=date,
        status_filter=status,
        search=search
    )


@router.get("/{booking_id}", summary="Admin: Xem chi tiết đơn vé điện tử")
def admin_get_booking_detail(
    booking_id: int,
    db: Session = Depends(get_db)
):
    """Lấy thông tin chi tiết một đơn vé điện tử cụ thể."""
    return booking_service.admin_get_booking_by_id(db=db, booking_id=booking_id)


@router.put("/{booking_id}/cancel", summary="Admin: Hủy vé & giải phóng ghế")
def admin_cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db)
):
    """
    Hủy vé cho Quản trị viên:
    - Cập nhật trạng thái đơn sang 'DA_HUY' (cancelled).
    - Giải phóng các ghế đã đặt trong suất chiếu để khách hàng khác có thể đặt.
    """
    return booking_service.admin_cancel_booking(db=db, booking_id=booking_id)


@router.post("/{booking_id}/cancel", summary="Admin: Hủy vé (POST alias)")
def admin_cancel_booking_post_alias(
    booking_id: int,
    db: Session = Depends(get_db)
):
    """Alias dạng POST cho chức năng hủy vé."""
    return booking_service.admin_cancel_booking(db=db, booking_id=booking_id)
