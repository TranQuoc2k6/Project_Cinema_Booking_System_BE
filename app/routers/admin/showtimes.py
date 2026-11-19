from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from app.schemas.showtime import (
    AdminShowtimeCreate,
    AdminShowtimeUpdate,
    AdminShowtimeResponse,
    AdminShowtimeListResponse,
)
from app.services import showtime_service

router = APIRouter(
    prefix="/showtimes",
    tags=["Admin: Showtimes"],
)


@router.get("", response_model=AdminShowtimeListResponse, summary="Admin: Danh sách suất chiếu (phân trang, lọc phim/rạp/ngày/trạng thái, tìm kiếm)")
def admin_get_showtimes(
    page: int = Query(1, ge=1, description="Số trang hiển thị"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng suất chiếu trên mỗi trang"),
    movie_id: Optional[int] = Query(None, description="Lọc theo ID phim"),
    cinema_id: Optional[int] = Query(None, description="Lọc theo ID cụm rạp"),
    room_id: Optional[int] = Query(None, description="Lọc theo ID phòng chiếu"),
    date: Optional[str] = Query(None, description="Lọc theo ngày chiếu (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên phim, tên rạp hoặc tên phòng chiếu"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: upcoming, ongoing, finished"),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách suất chiếu phục vụ trang Quản lý Suất chiếu của Admin:
    - Phân trang, tìm kiếm theo tên phim, cụm rạp, phòng chiếu
    - Lọc theo ngày chiếu, ID phim, ID cụm rạp, trạng thái
    - Kèm số lượng vé đã đặt
    """
    return showtime_service.admin_get_showtimes(
        db=db,
        page=page,
        limit=limit,
        movie_id=movie_id,
        cinema_id=cinema_id,
        room_id=room_id,
        date_str=date,
        search=search,
        status_filter=status,
    )


@router.get("/{showtime_id}", response_model=AdminShowtimeResponse, summary="Admin: Chi tiết một suất chiếu theo ID")
def admin_get_showtime_detail(
    showtime_id: int,
    db: Session = Depends(get_db),
):
    """Lấy chi tiết thông tin một suất chiếu kèm phim, phòng, rạp."""
    return showtime_service.admin_get_showtime_by_id(db=db, showtime_id=showtime_id)


@router.post("", response_model=AdminShowtimeResponse, status_code=status.HTTP_201_CREATED, summary="Admin: Tạo suất chiếu mới (chặn trùng giờ kèm 15 phút dọn phòng)")
def admin_create_showtime(
    showtime_in: AdminShowtimeCreate,
    db: Session = Depends(get_db),
):
    """
    API Tạo suất chiếu mới cho Admin:
    - Tự động tính thời điểm kết thúc nếu bỏ trống (theo thời lượng phim).
    - Validate nghiêm ngặt: thời gian kết thúc phải đủ thời lượng phim.
    - **Chặn trùng giờ chiếu trong cùng phòng**: kiểm tra khoảng thời gian chiếu + 15 phút dọn phòng.
      Nếu có suất chiếu khác trùng hoặc lấn vào khoảng 15 phút dọn phòng, hệ thống sẽ từ chối và báo chi tiết.
    - Trả về thông tin đầy đủ của suất chiếu vừa tạo.
    """
    return showtime_service.admin_create_showtime(db=db, showtime_in=showtime_in)


@router.put("/{showtime_id}", response_model=AdminShowtimeResponse, summary="Admin: Cập nhật / sửa suất chiếu (chặn trùng giờ)")
def admin_update_showtime(
    showtime_id: int,
    showtime_in: AdminShowtimeUpdate,
    db: Session = Depends(get_db),
):
    """
    API Sửa thông tin suất chiếu:
    - Cho phép thay đổi phim, phòng, thời gian bắt đầu, thời gian kết thúc, giá vé.
    - Kiểm tra chặn trùng giờ chiếu (thời lượng phim + 15 phút dọn phòng) trong cùng phòng, loại trừ chính suất chiếu đang sửa.
    """
    return showtime_service.admin_update_showtime(db=db, showtime_id=showtime_id, showtime_in=showtime_in)


@router.patch("/{showtime_id}", response_model=AdminShowtimeResponse, summary="Admin: Cập nhật một phần suất chiếu (PATCH)")
def admin_patch_showtime(
    showtime_id: int,
    showtime_in: AdminShowtimeUpdate,
    db: Session = Depends(get_db),
):
    """API PATCH cập nhật suất chiếu (tương tự PUT)."""
    return showtime_service.admin_update_showtime(db=db, showtime_id=showtime_id, showtime_in=showtime_in)


@router.delete("/{showtime_id}", summary="Admin: Hủy / Xóa suất chiếu")
def admin_delete_showtime(
    showtime_id: int,
    force: bool = Query(False, description="Bắt buộc xóa ngay cả khi có vé đã đặt"),
    db: Session = Depends(get_db),
):
    """
    API Hủy / Xóa suất chiếu khỏi hệ thống:
    - Nếu đã có vé được thanh toán (DA_THANH_TOAN / CONFIRMED) và không có cờ force=True, hệ thống sẽ cảnh báo không cho xóa.
    - Giải phóng lịch chiếu trong phòng.
    """
    return showtime_service.admin_delete_showtime(db=db, showtime_id=showtime_id, force=force)


@router.post("/{showtime_id}/cancel", summary="Admin: Hủy suất chiếu (POST alias)")
def admin_cancel_showtime_post_alias(
    showtime_id: int,
    force: bool = Query(False, description="Bắt buộc hủy ngay cả khi có vé đã đặt"),
    db: Session = Depends(get_db),
):
    """Alias dạng POST cho chức năng hủy suất chiếu."""
    return showtime_service.admin_delete_showtime(db=db, showtime_id=showtime_id, force=force)
