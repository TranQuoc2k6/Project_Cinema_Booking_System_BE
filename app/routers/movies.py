
from datetime import date, datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from app.models.movie import Movie
from app.models.showtime import Showtime

router = APIRouter(tags=["Movies"])


@router.get("/movies")
def get_movies(
    status: Optional[Literal["now_showing", "coming_soon"]] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    today = date.today()
    now = datetime.now()

    query = db.query(Movie)

    # Lọc phim theo trạng thái
    if status == "coming_soon":
        query = query.filter(Movie.release_date > today)

    elif status == "now_showing":
        query = query.filter(
            Movie.release_date <= today,
            Movie.showtimes.any(Showtime.end_time >= now)
        )

    # Đếm tổng số phim sau khi lọc
    total = query.count()

    # Tính vị trí bắt đầu lấy dữ liệu
    offset = (page - 1) * limit

    # Lấy danh sách phim theo trang
    movies = (
        query
        .order_by(Movie.release_date.desc(), Movie.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Chuyển dữ liệu phim thành JSON
    items = []

    for movie in movies:
        if movie.release_date > today:
            movie_status = "coming_soon"
        elif any(showtime.end_time >= now for showtime in movie.showtimes):
            movie_status = "now_showing"
        else:
            movie_status = "ended"

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

    total_pages = (total + limit - 1) // limit

    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    }
