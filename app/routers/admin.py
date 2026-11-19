from typing import List, Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.movie import Movie
from app.models.booking import Booking
from app.models.payment import Payment
from app.schemas.user import UserResponse
from app.schemas.movie import (
    AdminMovieCreate,
    AdminMovieUpdate,
    AdminMovieStatusUpdate,
    AdminMovieResponse,
    AdminMovieListResponse,
)
from app.schemas.showtime import (
    AdminShowtimeCreate,
    AdminShowtimeUpdate,
    AdminShowtimeResponse,
    AdminShowtimeListResponse,
)
from app.services import movie_service, booking_service, user_service, dashboard_service, showtime_service
from pydantic import BaseModel


class UserStatusUpdate(BaseModel):
    is_active: Optional[bool] = None

router = APIRouter(
    tags=["Admin Portal"],
    dependencies=[Depends(require_admin)],  # Toàn bộ router này được bảo vệ bởi require_admin
)


@router.get("/check-admin", summary="Kiểm tra xác thực quyền Quản trị viên (Admin Guard)")
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


@router.get("/dashboard/stats", summary="Thống kê toàn diện Dashboard Quản trị (Doanh thu, Vé bán, Lấp đầy, Theo phim)")
def get_dashboard_stats(
    days: int = Query(7, ge=1, le=90, description="Khoảng thời gian thống kê (7, 14, 30 ngày)"),
    db: Session = Depends(get_db)
):
    """
    Cung cấp số liệu thống kê phân tích thời gian thực dành cho Quản trị viên (SRS 1.4):
    - Thẻ chỉ số KPI (Tổng doanh thu, Doanh thu hôm nay, Vé bán, Tỷ lệ lấp đầy TB, Phim chiếu, Khách hàng)
    - Thống kê Doanh thu & Số vé bán theo ngày (kèm dữ liệu biểu đồ)
    - Thống kê Doanh thu & Số vé bán theo từng bộ phim (Box office)
    - Tỷ lệ lấp đầy theo suất chiếu / phòng chiếu (Occupancy Rate)
    - Danh sách đơn đặt vé trực tuyến mới nhất
    """
    try:
        return dashboard_service.get_dashboard_full_stats(db=db, days=days)
    except Exception as e:
        # Fallback an toàn nếu có lỗi kết nối đột ngột
        return {
            "status": "error",
            "message": str(e),
            "data": {
                "total_revenue": 0.0,
                "today_revenue": 0.0,
                "total_tickets": 0,
                "today_tickets": 0,
                "total_movies": 0,
                "total_users": 0,
                "occupancy_rate": 0.0,
                "kpi": {
                    "total_revenue": 0.0,
                    "today_revenue": 0.0,
                    "total_tickets": 0,
                    "today_tickets": 0,
                    "total_movies": 0,
                    "total_users": 0,
                    "avg_occupancy_rate": 0.0,
                    "top_movie": None
                },
                "revenue_by_day": [],
                "revenue_by_movie": [],
                "occupancy_by_showtime": [],
                "recent_bookings": []
            }
        }


# ============================================================================
# API QUẢN TRỊ KHÁCH HÀNG & NGƯỜI DÙNG (DANH SÁCH, TÌM KIẾM, KHÓA/MỞ TÀI KHOẢN)
# ============================================================================

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


# ============================================================================
# API QUẢN TRỊ DANH MỤC PHIM (THÊM / SỬA / NGỪNG CHIẾU / GÁN THỂ LOẠI)
# ============================================================================

@router.get("/movies", response_model=AdminMovieListResponse, summary="Admin: Danh sách phim phân trang & tìm kiếm")
def admin_get_movies_list(
    page: int = Query(1, ge=1, description="Số trang hiển thị"),
    limit: int = Query(10, ge=1, le=100, description="Số lượng phim trên mỗi trang"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: all, now_showing, coming_soon, ended"),
    search: Optional[str] = Query(None, description="Từ khóa tìm kiếm theo tên phim"),
    genre_id: Optional[int] = Query(None, ge=1, description="Lọc theo ID thể loại"),
    sort_order: Literal["asc", "desc"] = Query("desc", description="Thứ tự sắp xếp theo ngày phát hành"),
    db: Session = Depends(get_db)
):
    """
    API lấy danh sách phim phục vụ trang Quản lý Danh mục Phim của Admin:
    - Có phân trang (page, limit)
    - Tìm kiếm theo tên phim
    - Lọc theo trạng thái và thể loại
    - Trả về đầy đủ danh sách thể loại (genres) đã gán cho từng phim
    """
    return movie_service.admin_get_movies(
        db=db,
        page=page,
        limit=limit,
        search=search,
        status_filter=status,
        genre_id=genre_id,
        sort_order=sort_order
    )


@router.get("/movies/{movie_id}", response_model=AdminMovieResponse, summary="Admin: Chi tiết phim theo ID")
def admin_get_movie_detail(
    movie_id: int,
    db: Session = Depends(get_db)
):
    """Lấy thông tin chi tiết một bộ phim kèm thể loại dành cho Admin."""
    return movie_service.admin_get_movie_by_id(db=db, movie_id=movie_id)


@router.post("/movies", response_model=AdminMovieResponse, status_code=status.HTTP_201_CREATED, summary="Admin: Thêm phim mới & gán thể loại")
def admin_create_movie(
    movie_in: AdminMovieCreate,
    db: Session = Depends(get_db)
):
    """
    API Thêm phim mới vào hệ thống:
    - Validate nghiêm ngặt:
        + Tên phim (title) không được để trống.
        + Thời lượng phim (duration / duration_minutes) bắt buộc và phải > 0 phút.
        + Ngày khởi chiếu (release_date) bắt buộc đúng định dạng YYYY-MM-DD.
    - Gán danh sách thể loại qua `genre_ids` (kiểm tra tồn tại từng ID trong DB).
    - Tự động sinh slug duy nhất và gán trạng thái công chiếu.
    """
    return movie_service.admin_create_movie(db=db, movie_in=movie_in)


@router.put("/movies/{movie_id}", response_model=AdminMovieResponse, summary="Admin: Chỉnh sửa thông tin phim & thể loại")
def admin_update_movie(
    movie_id: int,
    movie_in: AdminMovieUpdate,
    db: Session = Depends(get_db)
):
    """
    API Chỉnh sửa thông tin phim:
    - Cho phép cập nhật tên phim, thời lượng, ngày khởi chiếu, poster, trailer, mô tả.
    - Validate thời lượng > 0 nếu có truyền.
    - Cập nhật lại danh sách thể loại phim qua `genre_ids`.
    """
    return movie_service.admin_update_movie(db=db, movie_id=movie_id, movie_in=movie_in)


@router.patch("/movies/{movie_id}", response_model=AdminMovieResponse, summary="Admin: Cập nhật một phần thông tin phim")
def admin_patch_movie(
    movie_id: int,
    movie_in: AdminMovieUpdate,
    db: Session = Depends(get_db)
):
    """API PATCH cập nhật một phần dữ liệu phim (tương tự PUT)."""
    return movie_service.admin_update_movie(db=db, movie_id=movie_id, movie_in=movie_in)


@router.patch("/movies/{movie_id}/stop", summary="Admin: Ngừng chiếu phim (chuyển sang 'ended')")
def admin_stop_movie(
    movie_id: int,
    db: Session = Depends(get_db)
):
    """
    API Ngừng chiếu phim:
    - Chuyển trạng thái bộ phim sang 'ended'.
    - Khi đó phim không còn xuất hiện trong danh sách Now Showing của khách hàng.
    """
    return movie_service.admin_stop_movie(db=db, movie_id=movie_id)


@router.post("/movies/{movie_id}/stop", summary="Admin: Ngừng chiếu phim (POST alias)")
def admin_stop_movie_post_alias(
    movie_id: int,
    db: Session = Depends(get_db)
):
    """Alias dạng POST cho chức năng ngừng chiếu phim để thuận tiện tích hợp form/webhook."""
    return movie_service.admin_stop_movie(db=db, movie_id=movie_id)


@router.patch("/movies/{movie_id}/status", summary="Admin: Điều chỉnh trạng thái phim linh hoạt")
def admin_update_movie_status(
    movie_id: int,
    status_in: AdminMovieStatusUpdate,
    db: Session = Depends(get_db)
):
    """
    API Điều chỉnh trạng thái phim:
    - Chỉ chấp nhận các giá trị: 'now_showing', 'coming_soon', 'ended'.
    """
    return movie_service.admin_update_movie_status(db=db, movie_id=movie_id, new_status=status_in.status)


@router.delete("/movies/{movie_id}", summary="Admin: Xóa phim khỏi hệ thống")
def admin_delete_movie(
    movie_id: int,
    db: Session = Depends(get_db)
):
    """API Xóa bộ phim khỏi cơ sở dữ liệu."""
    return movie_service.admin_delete_movie(db=db, movie_id=movie_id)


@router.post("/movies/upload-poster", summary="Admin: Upload ảnh Poster phim (.jpg/.png, tối đa 5MB)")
def admin_upload_movie_poster(
    file: UploadFile = File(..., description="File ảnh poster định dạng .jpg, .jpeg, .png (tối đa 5MB)")
):
    """
    API Upload Poster phim dành cho Quản trị viên (SRS 1.2):
    - Tiếp nhận ảnh định dạng .jpg, .jpeg, .png
    - Giới hạn dung lượng tối đa 5MB
    - Lưu file vào thư mục tĩnh uploads/posters/
    - Trả về URL ảnh để lưu vào database và xem trước
    """
    return movie_service.save_movie_poster(file=file)


# ============================================================================
# API QUẢN TRỊ ĐƠN VÉ (DANH SÁCH, LỌC PHIM/NGÀY/TRẠNG THÁI, TÌM KIẾM, HỦY VÉ)
# ============================================================================

@router.get("/bookings", summary="Admin: Danh sách đơn vé (lọc phim/ngày/trạng thái, tìm theo mã vé/SĐT)")
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


@router.get("/bookings/{booking_id}", summary="Admin: Xem chi tiết đơn vé điện tử")
def admin_get_booking_detail(
    booking_id: int,
    db: Session = Depends(get_db)
):
    """Lấy thông tin chi tiết một đơn vé điện tử cụ thể."""
    return booking_service.admin_get_booking_by_id(db=db, booking_id=booking_id)


@router.put("/bookings/{booking_id}/cancel", summary="Admin: Hủy vé & giải phóng ghế")
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


@router.post("/bookings/{booking_id}/cancel", summary="Admin: Hủy vé (POST alias)")
def admin_cancel_booking_post_alias(
    booking_id: int,
    db: Session = Depends(get_db)
):
    """Alias dạng POST cho chức năng hủy vé."""
    return booking_service.admin_cancel_booking(db=db, booking_id=booking_id)


# ============================================================================
# API QUẢN TRỊ SUẤT CHIẾU & CHẶN TRÙNG GIỜ (TẠO / SỬA / HỦY)
# ============================================================================

@router.get("/showtimes", response_model=AdminShowtimeListResponse, summary="Admin: Danh sách suất chiếu (phân trang, lọc phim/rạp/ngày/trạng thái, tìm kiếm)")
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


@router.get("/showtimes/{showtime_id}", response_model=AdminShowtimeResponse, summary="Admin: Chi tiết một suất chiếu theo ID")
def admin_get_showtime_detail(
    showtime_id: int,
    db: Session = Depends(get_db),
):
    """Lấy chi tiết thông tin một suất chiếu kèm phim, phòng, rạp."""
    return showtime_service.admin_get_showtime_by_id(db=db, showtime_id=showtime_id)


@router.post("/showtimes", response_model=AdminShowtimeResponse, status_code=status.HTTP_201_CREATED, summary="Admin: Tạo suất chiếu mới (chặn trùng giờ kèm 15 phút dọn phòng)")
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


@router.put("/showtimes/{showtime_id}", response_model=AdminShowtimeResponse, summary="Admin: Cập nhật / sửa suất chiếu (chặn trùng giờ)")
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


@router.patch("/showtimes/{showtime_id}", response_model=AdminShowtimeResponse, summary="Admin: Cập nhật một phần suất chiếu (PATCH)")
def admin_patch_showtime(
    showtime_id: int,
    showtime_in: AdminShowtimeUpdate,
    db: Session = Depends(get_db),
):
    """API PATCH cập nhật suất chiếu (tương tự PUT)."""
    return showtime_service.admin_update_showtime(db=db, showtime_id=showtime_id, showtime_in=showtime_in)


@router.delete("/showtimes/{showtime_id}", summary="Admin: Hủy / Xóa suất chiếu")
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


@router.post("/showtimes/{showtime_id}/cancel", summary="Admin: Hủy suất chiếu (POST alias)")
def admin_cancel_showtime_post_alias(
    showtime_id: int,
    force: bool = Query(False, description="Bắt buộc hủy ngay cả khi có vé đã đặt"),
    db: Session = Depends(get_db),
):
    """Alias dạng POST cho chức năng hủy suất chiếu."""
    return showtime_service.admin_delete_showtime(db=db, showtime_id=showtime_id, force=force)



