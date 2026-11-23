from typing import Optional, Literal
from fastapi import APIRouter, Depends, Query, UploadFile, File, status
from sqlalchemy.orm import Session

from database import get_db
from app.schemas.movie import (
    AdminMovieCreate,
    AdminMovieUpdate,
    AdminMovieStatusUpdate,
    AdminMovieResponse,
    AdminMovieListResponse,
)
from app.services import movie_service

router = APIRouter(
    prefix="/movies",
    tags=["Admin: Movies"],
)


@router.post("/upload-poster", summary="Admin: Upload ảnh Poster phim (.jpg/.png, tối đa 5MB)")
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


@router.get("", response_model=AdminMovieListResponse, summary="Admin: Danh sách phim phân trang & tìm kiếm")
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


@router.get("/{movie_id}", response_model=AdminMovieResponse, summary="Admin: Chi tiết phim theo ID")
def admin_get_movie_detail(
    movie_id: int,
    db: Session = Depends(get_db)
):
    """Lấy thông tin chi tiết một bộ phim kèm thể loại dành cho Admin."""
    return movie_service.admin_get_movie_by_id(db=db, movie_id=movie_id)


@router.post("", response_model=AdminMovieResponse, status_code=status.HTTP_201_CREATED, summary="Admin: Thêm phim mới & gán thể loại")
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


@router.put("/{movie_id}", response_model=AdminMovieResponse, summary="Admin: Chỉnh sửa thông tin phim & thể loại")
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


@router.patch("/{movie_id}", response_model=AdminMovieResponse, summary="Admin: Cập nhật một phần thông tin phim")
def admin_patch_movie(
    movie_id: int,
    movie_in: AdminMovieUpdate,
    db: Session = Depends(get_db)
):
    """API PATCH cập nhật một phần dữ liệu phim (tương tự PUT)."""
    return movie_service.admin_update_movie(db=db, movie_id=movie_id, movie_in=movie_in)


@router.patch("/{movie_id}/stop", summary="Admin: Ngừng chiếu phim (chuyển sang 'ended')")
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


@router.post("/{movie_id}/stop", summary="Admin: Ngừng chiếu phim (POST alias)")
def admin_stop_movie_post_alias(
    movie_id: int,
    db: Session = Depends(get_db)
):
    """Alias dạng POST cho chức năng ngừng chiếu phim để thuận tiện tích hợp form/webhook."""
    return movie_service.admin_stop_movie(db=db, movie_id=movie_id)


@router.patch("/{movie_id}/status", summary="Admin: Điều chỉnh trạng thái phim linh hoạt")
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


@router.delete("/{movie_id}", summary="Admin: Xóa phim khỏi hệ thống")
def admin_delete_movie(
    movie_id: int,
    db: Session = Depends(get_db)
):
    """API Xóa bộ phim khỏi cơ sở dữ liệu."""
    return movie_service.admin_delete_movie(db=db, movie_id=movie_id)
