from typing import Literal, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from app.schemas.movie import MovieCreate, MovieUpdate, MovieItemResponse, MovieListResponse
from app.services import movie_service

router = APIRouter(
    prefix="/api/movies",
    tags=["Movies"]
)



@router.get("", response_model=MovieListResponse)
def get_movies(
    status: Optional[Literal["now_showing", "coming_soon"]] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    genre_id: Optional[int] = Query(None, ge=1),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    db: Session = Depends(get_db)
):
    return movie_service.get_movies(
        db=db,
        status_filter=status,
        page=page,
        limit=limit,
        search=search,
        genre_id=genre_id,
        sort_order=sort_order
    )
    


@router.get("/{movie_id}", response_model=MovieItemResponse)
def get_movie_by_id(movie_id: int, db: Session = Depends(get_db)):
    return movie_service.get_movie_by_id(db=db, movie_id=movie_id)


@router.post("", response_model=MovieItemResponse, status_code=status.HTTP_201_CREATED)
def create_movie(movie_data: MovieCreate, db: Session = Depends(get_db)):
    return movie_service.create_movie(db=db, movie_data=movie_data)


@router.put("/{movie_id}", response_model=MovieItemResponse)
def update_movie(
    movie_id: int,
    movie_data: MovieUpdate,
    db: Session = Depends(get_db)
):
    return movie_service.update_movie(db=db, movie_id=movie_id, movie_data=movie_data)


@router.delete("/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_movie(movie_id: int, db: Session = Depends(get_db)):
    return movie_service.delete_movie(db=db, movie_id=movie_id)