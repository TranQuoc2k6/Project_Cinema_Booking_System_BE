import re
import unicodedata
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.movie import Movie
from app.models.showtime import Showtime
from app.models.genre import Genre
from app.schemas.movie import (
    MovieCreate,
    MovieUpdate,
    AdminMovieCreate,
    AdminMovieUpdate,
    AdminMovieResponse,
    AdminMovieListResponse,
)


def get_movie_status(movie: Movie, today: Optional[date] = None, now: Optional[datetime] = None) -> str:
    """
    Xác định trạng thái của phim:
    - Nếu admin đã đánh dấu 'ENDED' / ngừng chiếu -> 'ended'
    - Nếu ngày khởi chiếu > hôm nay -> 'coming_soon'
    - Nếu có suất chiếu kết thúc sau thời điểm hiện tại hoặc cờ NOW_SHOWING -> 'now_showing'
    - Ngược lại -> 'ended'
    """
    if today is None:
        today = date.today()
    if now is None:
        now = datetime.now()

    # Nếu trạng thái lưu trong DB là đã kết thúc / ngừng chiếu
    if movie.status and str(movie.status).strip().upper() in ["ENDED", "NGUNG_CHIEU"]:
        return "ended"

    # Kiểm tra ngày khởi chiếu
    if movie.release_date and movie.release_date > today:
        return "coming_soon"

    # Kiểm tra suất chiếu còn hiệu lực
    if movie.showtimes and any(showtime.end_time >= now for showtime in movie.showtimes):
        return "now_showing"

    # Nếu admin lưu cờ NOW_SHOWING rõ ràng
    if movie.status and str(movie.status).strip().upper() in ["NOW_SHOWING", "DANG_CHIEU"]:
        return "now_showing"

    return "ended"


def create_slug(title: str) -> str:
    """Chuyển đổi tiêu đề phim tiếng Việt thành slug URL an toàn."""
    title = title.lower()
    title = title.replace("đ", "d")
    title = unicodedata.normalize("NFKD", title)
    title = title.encode("ascii", "ignore").decode("utf-8")
    title = re.sub(r"[^a-z0-9]+", "-", title)
    return title.strip("-")


def format_admin_movie(movie: Movie, today: Optional[date] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Helper format thực thể Movie thành dict dữ liệu trả về cho Admin kèm mảng genres."""
    movie_status = get_movie_status(movie, today, now)
    genres_data = [
        {"id": g.id, "name": g.name}
        for g in (movie.genres or [])
    ]
    return {
        "id": movie.id,
        "title": movie.title,
        "slug": movie.slug,
        "description": movie.description,
        "duration_minutes": movie.duration_minutes or 120,
        "release_date": movie.release_date,
        "poster_url": movie.poster_url,
        "trailer_url": movie.trailer_url,
        "age_rating": getattr(movie, "age_rating", "P") or "P",
        "status": movie_status,
        "genres": genres_data,
    }


# ============================================================================
# CÁC HÀM XỬ LÝ PHIM DÀNH CHO KHÁCH HÀNG (PUBLIC API)
# ============================================================================

def get_movies(
    db: Session,
    status_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None,
    genre_id: Optional[int] = None,
    sort_order: str = "desc"
):
    today = date.today()
    now = datetime.now()

    query = db.query(Movie)

    # Lọc theo trạng thái
    if status_filter == "coming_soon":
        query = query.filter(Movie.release_date > today)
    elif status_filter == "now_showing":
        query = query.filter(
            Movie.release_date <= today,
            Movie.showtimes.any(Showtime.end_time >= now)
        )
    elif status_filter == "ended":
        query = query.filter(
            (Movie.status.in_(["ENDED", "ended"])) |
            (Movie.release_date <= today)
        )

    # Tìm kiếm theo tên phim
    if search:
        query = query.filter(Movie.title.ilike(f"%{search.strip()}%"))

    # Lọc theo thể loại
    if genre_id is not None:
        query = query.filter(Movie.genres.any(Genre.id == genre_id))

    total = query.count()

    # Sắp xếp
    if sort_order == "asc":
        query = query.order_by(Movie.release_date.asc(), Movie.id.asc())
    else:
        query = query.order_by(Movie.release_date.desc(), Movie.id.desc())

    offset = (page - 1) * limit
    movies = query.offset(offset).limit(limit).all()

    items = []
    for movie in movies:
        movie_status = get_movie_status(movie, today, now)
        items.append({
            "id": movie.id,
            "title": movie.title,
            "slug": movie.slug,
            "description": movie.description,
            "duration_minutes": movie.duration_minutes,
            "release_date": movie.release_date,
            "poster_url": movie.poster_url,
            "trailer_url": movie.trailer_url,
            "status": movie_status
        })

    total_pages = (total + limit - 1) // limit if limit > 0 else 1

    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    }


def get_movie_by_id(db: Session, movie_id: int):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
    
    today = date.today()
    now = datetime.now()
    movie_status = get_movie_status(movie, today, now)

    return {
        "id": movie.id,
        "title": movie.title,
        "slug": movie.slug,
        "description": movie.description,
        "duration_minutes": movie.duration_minutes,
        "release_date": movie.release_date,
        "poster_url": movie.poster_url,
        "trailer_url": movie.trailer_url,
        "status": movie_status
    }


def create_movie(db: Session, movie_data: MovieCreate):
    slug = create_slug(movie_data.title)
    existing = db.query(Movie).filter(Movie.slug == slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie already exists"
        )

    genres = []
    if movie_data.genre_ids:
        genres = db.query(Genre).filter(Genre.id.in_(movie_data.genre_ids)).all()
        if len(genres) != len(set(movie_data.genre_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Genre not found"
            )

    duration_val = movie_data.duration if movie_data.duration is not None else movie_data.duration_minutes
    if duration_val is None or duration_val <= 0:
        duration_val = 120

    new_movie = Movie(
        title=movie_data.title,
        slug=slug,
        description=movie_data.description,
        duration_minutes=duration_val,
        release_date=movie_data.release_date or date.today(),
        poster_url=movie_data.poster_url or movie_data.poster,
        trailer_url=movie_data.trailer_url or movie_data.trailer,
        status=movie_data.status or "NOW_SHOWING",
        genres=genres
    )

    db.add(new_movie)
    db.commit()
    db.refresh(new_movie)

    today = date.today()
    now = datetime.now()
    movie_status = get_movie_status(new_movie, today, now)

    return {
        "id": new_movie.id,
        "title": new_movie.title,
        "slug": new_movie.slug,
        "description": new_movie.description,
        "duration_minutes": new_movie.duration_minutes,
        "release_date": new_movie.release_date,
        "poster_url": new_movie.poster_url,
        "trailer_url": new_movie.trailer_url,
        "status": movie_status
    }


def update_movie(db: Session, movie_id: int, movie_data: MovieUpdate):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )

    update_dict = movie_data.model_dump(exclude_unset=True)

    if "title" in update_dict and update_dict["title"]:
        new_title = update_dict["title"]
        new_slug = create_slug(new_title)
        existing = db.query(Movie).filter(
            Movie.slug == new_slug,
            Movie.id != movie_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Movie already exists"
            )
        movie.slug = new_slug

    if "duration" in update_dict:
        dur = update_dict.pop("duration")
        if dur is not None and dur > 0:
            movie.duration_minutes = dur
    if "duration_minutes" in update_dict:
        dur = update_dict.pop("duration_minutes")
        if dur is not None and dur > 0:
            movie.duration_minutes = dur

    if "poster" in update_dict:
        movie.poster_url = update_dict.pop("poster")
    if "poster_url" in update_dict:
        movie.poster_url = update_dict.pop("poster_url")

    if "trailer" in update_dict:
        movie.trailer_url = update_dict.pop("trailer")
    if "trailer_url" in update_dict:
        movie.trailer_url = update_dict.pop("trailer_url")

    if "genre_ids" in update_dict:
        genre_ids = update_dict.pop("genre_ids")
        if genre_ids is not None:
            genres = db.query(Genre).filter(Genre.id.in_(genre_ids)).all()
            if len(genres) != len(set(genre_ids)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Genre not found"
                )
            movie.genres = genres

    for key, value in update_dict.items():
        setattr(movie, key, value)

    db.commit()
    db.refresh(movie)

    today = date.today()
    now = datetime.now()
    movie_status = get_movie_status(movie, today, now)

    return {
        "id": movie.id,
        "title": movie.title,
        "slug": movie.slug,
        "description": movie.description,
        "duration_minutes": movie.duration_minutes,
        "release_date": movie.release_date,
        "poster_url": movie.poster_url,
        "trailer_url": movie.trailer_url,
        "status": movie_status
    }


def delete_movie(db: Session, movie_id: int):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
    db.delete(movie)
    db.commit()
    return None


# ============================================================================
# CÁC HÀM XỬ LÝ DÀNH RIÊNG CHO ADMIN PORTAL (SRS TASK /ADMIN/MOVIES)
# ============================================================================

def admin_create_movie(db: Session, movie_in: AdminMovieCreate) -> Dict[str, Any]:
    """
    Thêm phim mới cho Admin:
    - Bắt buộc & validate: title, duration_minutes > 0, release_date.
    - Gán danh sách thể loại (genre_ids), kiểm tra tồn tại từng ID trong DB.
    - Tự động sinh slug duy nhất, gán trạng thái và lưu DB.
    """
    # 1. Validate title
    title = movie_in.title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên phim không được để trống hoặc chỉ chứa khoảng trắng."
        )

    # 2. Validate duration > 0
    try:
        duration = movie_in.resolve_duration()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # 3. Validate release_date
    if not movie_in.release_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày khởi chiếu (release_date) là bắt buộc."
        )

    # 4. Validate & liên kết thể loại (genre_ids)
    genres: List[Genre] = []
    if movie_in.genre_ids:
        unique_genre_ids = list(dict.fromkeys(movie_in.genre_ids))
        genres = db.query(Genre).filter(Genre.id.in_(unique_genre_ids)).all()
        found_ids = {g.id for g in genres}
        missing_ids = [gid for gid in unique_genre_ids if gid not in found_ids]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Thể loại với ID {missing_ids} không tồn tại trong hệ thống."
            )

    # 5. Sinh slug duy nhất
    base_slug = create_slug(title)
    slug = base_slug
    counter = 1
    while db.query(Movie).filter(Movie.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    # 6. Chuẩn hóa trạng thái ban đầu
    raw_status = (movie_in.status or "NOW_SHOWING").strip().upper()
    if raw_status in ["COMING_SOON", "SAP_CHIEU"]:
        initial_status = "COMING_SOON"
    elif raw_status in ["ENDED", "NGUNG_CHIEU"]:
        initial_status = "ENDED"
    else:
        initial_status = "NOW_SHOWING"

    # 7. Khởi tạo đối tượng Movie
    new_movie = Movie(
        title=title,
        slug=slug,
        description=movie_in.description,
        duration_minutes=duration,
        release_date=movie_in.release_date,
        poster_url=movie_in.resolve_poster(),
        trailer_url=movie_in.resolve_trailer(),
        status=initial_status,
        genres=genres
    )

    db.add(new_movie)
    db.commit()
    db.refresh(new_movie)

    return format_admin_movie(new_movie)


def admin_update_movie(db: Session, movie_id: int, movie_in: AdminMovieUpdate) -> Dict[str, Any]:
    """
    Sửa thông tin phim cho Admin:
    - Cho phép sửa title, duration, release_date, poster, trailer, description, status, genre_ids.
    - Validate thời lượng > 0 nếu có truyền.
    - Cập nhật lại mối quan hệ thể loại n-n.
    """
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bộ phim với ID = {movie_id}."
        )

    # 1. Cập nhật title và sinh lại slug nếu có
    if movie_in.title is not None:
        title = movie_in.title.strip()
        if not title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên phim không được để trống hoặc chỉ chứa khoảng trắng."
            )
        movie.title = title
        base_slug = create_slug(title)
        slug = base_slug
        existing = db.query(Movie).filter(Movie.slug == slug, Movie.id != movie_id).first()
        if existing:
            slug = f"{base_slug}-{movie_id}"
        movie.slug = slug

    # 2. Cập nhật duration
    dur = movie_in.resolve_duration()
    if dur is not None:
        if dur <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thời lượng phim phải lớn hơn 0 phút."
            )
        movie.duration_minutes = dur

    # 3. Cập nhật release_date
    if movie_in.release_date is not None:
        movie.release_date = movie_in.release_date

    # 4. Cập nhật description, poster, trailer
    if movie_in.description is not None:
        movie.description = movie_in.description
    if movie_in.resolve_poster() is not None:
        movie.poster_url = movie_in.resolve_poster()
    if movie_in.resolve_trailer() is not None:
        movie.trailer_url = movie_in.resolve_trailer()

    # 5. Cập nhật trạng thái
    if movie_in.status is not None:
        clean_status = movie_in.status.strip().upper()
        if clean_status in ["COMING_SOON", "SAP_CHIEU"]:
            movie.status = "COMING_SOON"
        elif clean_status in ["ENDED", "NGUNG_CHIEU"]:
            movie.status = "ENDED"
        else:
            movie.status = "NOW_SHOWING"

    # 6. Cập nhật gán thể loại
    if movie_in.genre_ids is not None:
        if len(movie_in.genre_ids) == 0:
            movie.genres = []
        else:
            unique_genre_ids = list(dict.fromkeys(movie_in.genre_ids))
            genres = db.query(Genre).filter(Genre.id.in_(unique_genre_ids)).all()
            found_ids = {g.id for g in genres}
            missing_ids = [gid for gid in unique_genre_ids if gid not in found_ids]
            if missing_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Thể loại với ID {missing_ids} không tồn tại trong hệ thống."
                )
            movie.genres = genres

    db.commit()
    db.refresh(movie)

    return format_admin_movie(movie)


def admin_stop_movie(db: Session, movie_id: int) -> Dict[str, Any]:
    """
    Ngừng chiếu phim (chuyển trạng thái sang 'ended'):
    - Đáp ứng yêu cầu chuyển trạng thái phim sang ngừng chiếu trong quản lý phim Admin.
    """
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bộ phim với ID = {movie_id}."
        )

    movie.status = "ENDED"
    db.commit()
    db.refresh(movie)

    return {
        "status": "success",
        "message": f"Đã chuyển trạng thái phim '{movie.title}' sang Ngừng chiếu (ended) thành công.",
        "movie_id": movie.id,
        "movie_title": movie.title,
        "movie_status": "ended",
        "movie": format_admin_movie(movie),
    }


def admin_update_movie_status(db: Session, movie_id: int, new_status: str) -> Dict[str, Any]:
    """Cập nhật linh hoạt trạng thái chiếu phim (now_showing, coming_soon, ended)."""
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bộ phim với ID = {movie_id}."
        )

    clean_status = new_status.strip().lower()
    if clean_status not in ["now_showing", "coming_soon", "ended"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trạng thái không hợp lệ. Chỉ chấp nhận: 'now_showing', 'coming_soon', 'ended'"
        )

    movie.status = clean_status.upper()
    db.commit()
    db.refresh(movie)

    return {
        "status": "success",
        "message": f"Cập nhật trạng thái phim '{movie.title}' thành '{clean_status}' thành công.",
        "movie_id": movie.id,
        "movie_title": movie.title,
        "movie_status": clean_status,
        "movie": format_admin_movie(movie),
    }


def admin_get_movies(
    db: Session,
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    genre_id: Optional[int] = None,
    sort_order: str = "desc"
) -> Dict[str, Any]:
    """Lấy danh sách phim phân trang & tìm kiếm dành cho trang Quản lý Phim Admin."""
    today = date.today()
    now = datetime.now()

    query = db.query(Movie)

    if status_filter and status_filter.lower() != "all":
        sf = status_filter.strip().lower()
        if sf == "coming_soon":
            query = query.filter(Movie.release_date > today, Movie.status != "ENDED")
        elif sf == "now_showing":
            query = query.filter(
                Movie.status != "ENDED",
                (Movie.release_date <= today) | (Movie.status == "NOW_SHOWING")
            )
        elif sf == "ended":
            query = query.filter(
                (Movie.status.in_(["ENDED", "ended"])) |
                (Movie.release_date <= today)
            )

    if search:
        query = query.filter(Movie.title.ilike(f"%{search.strip()}%"))

    if genre_id is not None:
        query = query.filter(Movie.genres.any(Genre.id == genre_id))

    total = query.count()

    if sort_order == "asc":
        query = query.order_by(Movie.release_date.asc(), Movie.id.asc())
    else:
        query = query.order_by(Movie.release_date.desc(), Movie.id.desc())

    offset = (page - 1) * limit
    movies = query.offset(offset).limit(limit).all()

    items = [format_admin_movie(m, today, now) for m in movies]
    total_pages = (total + limit - 1) // limit if limit > 0 else 1

    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
    }


def admin_get_movie_by_id(db: Session, movie_id: int) -> Dict[str, Any]:
    """Lấy thông tin chi tiết một bộ phim cho Admin."""
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bộ phim với ID = {movie_id}."
        )
    return format_admin_movie(movie)


def admin_delete_movie(db: Session, movie_id: int) -> Dict[str, Any]:
    """Xóa phim khỏi hệ thống."""
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bộ phim với ID = {movie_id}."
        )

    title = movie.title
    db.delete(movie)
    db.commit()

    return {
        "status": "success",
        "message": f"Đã xóa vĩnh viễn bộ phim '{title}' khỏi hệ thống.",
        "movie_id": movie_id
    }
