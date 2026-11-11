import re
import unicodedata

from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.movie import Movie
from app.models.showtime import Showtime
from app.schemas.movie import MovieCreate, MovieUpdate
from app.models.genre import Genre


def get_movie_status(movie: Movie, today: date, now: datetime) -> str:
    """Xác định trạng thái của phim: coming_soon, now_showing hoặc ended"""
    if movie.release_date > today:
        return "coming_soon"
    elif any(showtime.end_time >= now for showtime in movie.showtimes):
        return "now_showing"
    return "ended"



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

    # Tìm kiếm theo tên phim
    if search:
        query = query.filter(Movie.title.ilike(f"%{search.strip()}%"))

    # Lọc theo thể loại
    if genre_id is not None:
        query = query.filter(Movie.genres.any(Genre.id == genre_id))

    # Đếm tổng số phim sau khi lọc
    total = query.count()

    # Sắp xếp theo ngày phát hành
    if sort_order == "asc":
        query = query.order_by(Movie.release_date.asc(), Movie.id.asc())
    else:
        query = query.order_by(Movie.release_date.desc(), Movie.id.desc())

    # Phân trang
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

def create_slug(title: str):
    title = title.lower()
    title = title.replace("đ", "d")

    title = unicodedata.normalize("NFKD", title)
    title = title.encode("ascii", "ignore").decode("utf-8")

    title = re.sub(r"[^a-z0-9]+", "-", title)
    title = title.strip("-")

    return title

def create_movie(db: Session, movie_data: MovieCreate):
    # Tạo slug từ tên phim
    slug = create_slug(movie_data.title)

    # Kiểm tra slug đã tồn tại
    existing = db.query(Movie).filter(Movie.slug == slug).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie already exists"
        )

    # Lấy danh sách thể loại
    genres = []

    if movie_data.genre_ids:
        genres = db.query(Genre).filter(
            Genre.id.in_(movie_data.genre_ids)
        ).all()

        if len(genres) != len(set(movie_data.genre_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Genre not found"
            )

    # Tạo phim mới
    new_movie = Movie(
        title=movie_data.title,
        slug=slug,
        description=movie_data.description,
        duration_minutes=movie_data.duration,
        release_date=movie_data.release_date,
        poster_url=movie_data.poster,
        trailer_url=movie_data.trailer,
        age_rating=movie_data.age_rating,
        status=movie_data.status,
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

    # Chuyển tên trường Schema sang tên trường Model
    if "title" in update_dict:
        new_title = update_dict["title"]

        if new_title:
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
        movie.duration_minutes = update_dict.pop("duration")

    if "poster" in update_dict:
        movie.poster_url = update_dict.pop("poster")

    if "trailer" in update_dict:
        movie.trailer_url = update_dict.pop("trailer")

    if "genre_ids" in update_dict:
        genre_ids = update_dict.pop("genre_ids")

        if genre_ids is not None:
            genres = db.query(Genre).filter(
                Genre.id.in_(genre_ids)
            ).all()

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