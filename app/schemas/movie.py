from pydantic import BaseModel, Field, ConfigDict
from datetime import date
from typing import Optional, List
from app.schemas.genre import GenreResponse


class MovieCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None
    duration_minutes: Optional[int] = 120
    release_date: Optional[date] = None
    poster: Optional[str] = None
    poster_url: Optional[str] = None
    trailer: Optional[str] = None
    trailer_url: Optional[str] = None
    age_rating: Optional[str] = "P"
    status: Optional[str] = "NOW_SHOWING"
    genre_ids: List[int] = []


class MovieUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None
    duration_minutes: Optional[int] = None
    release_date: Optional[date] = None
    poster: Optional[str] = None
    poster_url: Optional[str] = None
    trailer: Optional[str] = None
    trailer_url: Optional[str] = None
    age_rating: Optional[str] = None
    status: Optional[str] = None
    genre_ids: Optional[List[int]] = None


class MovieItemResponse(BaseModel):
    id: int
    title: str
    slug: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    release_date: Optional[date] = None
    poster_url: Optional[str] = None
    trailer_url: Optional[str] = None
    status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MovieListResponse(BaseModel):
    items: List[MovieItemResponse] = []
    page: int = 1
    limit: int = 10
    total: int = 0
    total_pages: int = 1


class MovieResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    duration: Optional[int] = 120
    release_date: Optional[date] = None
    poster: Optional[str] = None
    trailer: Optional[str] = None
    age_rating: Optional[str] = "P"
    status: Optional[str] = "NOW_SHOWING"
    genres: List[GenreResponse] = []

    model_config = ConfigDict(from_attributes=True)
