from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from app.schemas.showtime import (
    AdminShowtimeCreate,
    AdminShowtimeUpdate,
    AdminShowtimeResponse,
    AdminShowtimeListResponse,
    PricingConfigResponse,
    PricingConfigUpdate,
)
from app.services import showtime_service
from app.core.pricing import get_pricing_config, update_pricing_config

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


# ============================================================================
# TỰ ĐỘNG SINH & DỌN DẸP SUẤT CHIẾU CHO ADMIN
# Khai báo trước /{showtime_id} để tránh match nhầm route
# ============================================================================

@router.post(
    "/auto-generate",
    summary="Admin: Tự động sinh suất chiếu thông minh cho các ngày tiếp theo",
    description="Tự động lập lịch phân bổ phim cho các phòng chiếu trong N ngày tiếp theo mà không bị trùng giờ, giúp admin không phải tạo thủ công.",
)
def admin_auto_generate_showtimes(
    days: int = Query(7, ge=1, le=14, description="Số ngày tiếp theo cần tự động sinh suất chiếu (mặc định: 7 ngày)"),
    db: Session = Depends(get_db),
):
    result = showtime_service.auto_generate_showtimes(db=db, days_ahead=days)
    return result


@router.post(
    "/cleanup-past",
    summary="Admin: Tự động dọn dẹp các suất chiếu phim cũ đã kết thúc",
    description="Xóa vĩnh viễn các suất chiếu cũ không có người mua vé để giải phóng lịch phòng và làm gọn CSDL.",
)
def admin_cleanup_past_showtimes(
    days: int = Query(0, ge=0, description="Số ngày trước hôm nay cần dọn dẹp (mặc định: 0, dọn các ngày trước hôm nay)"),
    db: Session = Depends(get_db),
):
    result = showtime_service.cleanup_past_showtimes(db=db, older_than_days=days)
    return result


# ============================================================================
# CẤU HÌNH GIÁ VÉ THEO LOẠI GHẾ & KHUNG GIỜ (SRS: GIÁ VÉ & PHỤ THU)
# Phải khai báo trước /{showtime_id} để tránh router match nhầm int param
# ============================================================================

@router.get("/pricing-config", response_model=PricingConfigResponse, summary="Admin: Xem cấu hình giá vé theo loại ghế & phụ thu")
def get_pricing_configuration():
    """
    Lấy cấu hình giá vé hiện tại của hệ thống:
    - Hệ số nhân theo loại ghế (Standard: 1.0, VIP: 1.5, Couple: 2.0).
    - Phụ thu cuối tuần (Thứ 7, Chủ Nhật, tối Thứ 6).
    - Phụ thu khung giờ vàng (18:00 - 22:00).
    """
    cfg = get_pricing_config()
    return PricingConfigResponse(
        seat_multipliers={k: float(v) for k, v in cfg["seat_multipliers"].items()},
        seat_type_surcharges={k: float(v) for k, v in cfg["seat_type_surcharges"].items()},
        weekend_surcharge=float(cfg["weekend_surcharge"]),
        peak_hour_surcharge=float(cfg["peak_hour_surcharge"]),
        peak_hour_start=cfg["peak_hour_start"],
        peak_hour_end=cfg["peak_hour_end"],
        weekend_days=cfg["weekend_days"],
        include_friday_evening=cfg["include_friday_evening"],
        friday_evening_start_hour=cfg["friday_evening_start_hour"],
    )


@router.put("/pricing-config", response_model=PricingConfigResponse, summary="Admin: Cập nhật cấu hình giá vé & phụ thu")
def update_pricing_configuration(config_in: PricingConfigUpdate):
    """
    Cập nhật chính sách giá vé:
    - Điều chỉnh hệ số giá theo loại ghế.
    - Cập nhật số tiền phụ thu cuối tuần (weekend_surcharge).
    - Cập nhật số tiền phụ thu giờ vàng (peak_hour_surcharge) và khung giờ.
    Thay đổi sẽ áp dụng ngay lập tức cho các suất chiếu và trang chọn ghế.
    """
    update_data = config_in.model_dump(exclude_unset=True)
    cfg = update_pricing_config(update_data)
    return PricingConfigResponse(
        seat_multipliers={k: float(v) for k, v in cfg["seat_multipliers"].items()},
        seat_type_surcharges={k: float(v) for k, v in cfg["seat_type_surcharges"].items()},
        weekend_surcharge=float(cfg["weekend_surcharge"]),
        peak_hour_surcharge=float(cfg["peak_hour_surcharge"]),
        peak_hour_start=cfg["peak_hour_start"],
        peak_hour_end=cfg["peak_hour_end"],
        weekend_days=cfg["weekend_days"],
        include_friday_evening=cfg["include_friday_evening"],
        friday_evening_start_hour=cfg["friday_evening_start_hour"],
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

