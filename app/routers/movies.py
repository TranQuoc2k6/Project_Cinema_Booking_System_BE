from datetime import date, datetime
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from database import get_db
from app.models.movie import Movie
from app.models.showtime import Showtime

router = APIRouter(
    prefix="/api/movies",
    tags=["Movies"]
)

# ------------------------------------------------------------------
# 1. PYDANTIC SCHEMAS (Validation & Swagger Docs)
# ------------------------------------------------------------------
class MovieBase(BaseModel):
    title: str
    description: Optional[str] = None
    duration_minutes: int
    release_date: date
    poster_url: Optional[str] = None
    trailer_url: Optional[str] = None

class MovieCreate(MovieBase):
    slug: str

class MovieUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    release_date: Optional[date] = None
    poster_url: Optional[str] = None
    trailer_url: Optional[str] = None

class MovieItemResponse(MovieBase):
    id: int
    slug: str
    status: str

    model_config = ConfigDict(from_attributes=True)

class MovieListResponse(BaseModel):
    items: List[MovieItemResponse]
    page: int
    limit: int
    total: int
    total_pages: int


# ------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# ------------------------------------------------------------------
def get_movie_status(movie: Movie, today: date, now: datetime) -> str:
    """Xác định trạng thái của phim: coming_soon, now_showing hoặc ended"""
    if movie.release_date > today:
        return "coming_soon"
    elif any(showtime.end_time >= now for showtime in movie.showtimes):
        return "now_showing"
    return "ended"


# ------------------------------------------------------------------
# 3. API ENDPOINTS
# ------------------------------------------------------------------

# GET /api/movies - Lấy danh sách phim (có phân trang & lọc theo status)
@router.get("", response_model=MovieListResponse)
def get_movies(
    status: Optional[Literal["now_showing", "coming_soon"]] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    today = date.today()
    now = datetime.now()

    query = db.query(Movie)

    if status == "coming_soon":
        query = query.filter(Movie.release_date > today)
    elif status == "now_showing":
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

    total_pages = (total + limit - 1) // limit

    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    }


# GET /api/movies/{movie_id} - Xem chi tiết 1 bộ phim
@router.get("/{movie_id}", response_model=MovieItemResponse)
def get_movie_by_id(movie_id: int, db: Session = Depends(get_db)):
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


# POST /api/movies - Tạo phim mới
@router.post("", response_model=MovieItemResponse, status_code=status.HTTP_201_CREATED)
def create_movie(movie_data: MovieCreate, db: Session = Depends(get_db)):
    # Kiểm tra trùng slug
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


# PUT /api/movies/{movie_id} - Cập nhật thông tin phim
@router.put("/{movie_id}", response_model=MovieItemResponse)
def update_movie(movie_id: int, movie_data: MovieUpdate, db: Session = Depends(get_db)):
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


# DELETE /api/movies/{movie_id} - Xóa phim
@router.delete("/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_movie(movie_id: int, db: Session = Depends(get_db)):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )

    db.delete(movie)
    db.commit()
    return None