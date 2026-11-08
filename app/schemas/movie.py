from pydantic import BaseModel, Field, ConfigDict
from datetime import date
from typing import Optional, List
from app.schemas.genre import GenreResponse


class MovieCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    duration: int = Field(..., gt=0)
    release_date: date
    poster: Optional[str] = None
    trailer: Optional[str] = None
    age_rating: str = Field(..., max_length=10)
    status: str = "COMING_SOON"
    genre_ids: List[int] = []


class MovieUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = Field(None, gt=0)
    release_date: Optional[date] = None
    poster: Optional[str] = None
    trailer: Optional[str] = None
    age_rating: Optional[str] = None
    status: Optional[str] = None
    genre_ids: Optional[List[int]] = None


class MovieResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    duration: int
    release_date: date
    poster: Optional[str] = None
    trailer: Optional[str] = None
    age_rating: str
    status: str
    genres: List[GenreResponse] = []

    model_config = ConfigDict(from_attributes=True)