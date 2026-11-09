from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.movies import router as movie_router

app = FastAPI()
app.include_router(movie_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

movies = [
    {"id": 1, "title": "Mai", "duration": 131},
    {"id": 2, "title": "Lat Mat 7", "duration": 138}
]

@app.get("/")
def home():
    return {"message": "Cinema Booking API is running"}

@app.get("/api/movies")
def get_movies():
    return movies

@app.post("/api/movies")
def create_movie(movie: dict):
    movie["id"] = len(movies) + 1
    movies.append(movie)
    return movie

@app.put("/api/movies/{movie_id}")
def update_movie(movie_id: int, updated_movie: dict):
    for movie in movies:
        if movie["id"] == movie_id:
            movie.update(updated_movie)
            return movie
    return {"message": "Movie not found"}

@app.delete("/api/movies/{movie_id}")
def delete_movie(movie_id: int):
    for movie in movies:
        if movie["id"] == movie_id:
            movies.remove(movie)
            return {"message": "Deleted successfully"}
    return {"message": "Movie not found"}