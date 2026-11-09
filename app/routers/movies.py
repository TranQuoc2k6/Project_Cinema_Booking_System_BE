from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(
    prefix="/api/movies",
    tags=["Movies"]
)

# Pydantic Schema giúp validate dữ liệu và hiển thị mẫu trên Swagger UI
class MovieBase(BaseModel):
    title: str
    duration: int

class MovieCreate(MovieBase):
    pass

class MovieResponse(MovieBase):
    id: int

# Mock Database tạm thời
movies_db = [
    {"id": 1, "title": "Mai", "duration": 131},
    {"id": 2, "title": "Lat Mat 7", "duration": 138}
]

@router.get("", response_model=List[MovieResponse])
def get_movies():
    return movies_db

@router.post("", response_model=MovieResponse, status_code=status.HTTP_201_CREATED)
def create_movie(movie: MovieCreate):
    new_id = max([m["id"] for m in movies_db], default=0) + 1
    new_movie = {"id": new_id, **movie.model_dump()}
    movies_db.append(new_movie)
    return new_movie

@router.put("/{movie_id}", response_model=MovieResponse)
def update_movie(movie_id: int, updated_movie: MovieCreate):
    for movie in movies_db:
        if movie["id"] == movie_id:
            movie.update(updated_movie.model_dump())
            return movie
    raise HTTPException(status_code=404, detail="Movie not found")

@router.delete("/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_movie(movie_id: int):
    for index, movie in enumerate(movies_db):
        if movie["id"] == movie_id:
            movies_db.pop(index)
            return
    raise HTTPException(status_code=404, detail="Movie not found")