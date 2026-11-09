from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.movie import Movie
from app.models.showtime import Showtime
from app.schemas.movie import MovieCreate, MovieUpdate


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
    limit: int = 10
):
    today = date.today()
    now = datetime.now()

    query = db.query(Movie)

    if status_filter == "coming_soon":
        query = query.filter(Movie.release_date > today)
    elif status_filter == "now_showing":
        query = query.filter(
            Movie.release_date <= today,
            Movie.showtimes.any(Showtime.end_time >= now)
        )

    total = query.count()
    offset = (page - 1) * limit

    movies = (
        query
        .order_by(Movie.release_date.desc(), Movie.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

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
    existing = db.query(Movie).filter(Movie.slug == movie_data.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slug already exists"
        )

    new_movie = Movie(**movie_data.model_dump())
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