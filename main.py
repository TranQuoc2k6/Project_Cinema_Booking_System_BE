from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, admin

app = FastAPI(
    title="Cinema Booking System API",
    description="Hệ thống Backend Đặt vé xem phim trực tuyến - Phân hệ Quản trị hệ thống & Bảo mật (Admin Portal & Security)",
    version="1.0.0",
)

# Cấu hình CORS cho phép Frontend truy cập từ mọi origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các Router xác thực và quản trị
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"], include_in_schema=False)

app.include_router(admin.router, prefix="/api/admin", tags=["Admin Portal"])
app.include_router(admin.router, prefix="/admin", tags=["Admin Portal"], include_in_schema=False)

# Dữ liệu mẫu ban đầu
movies = [
    {"id": 1, "title": "Mai", "duration": 131},
    {"id": 2, "title": "Lat Mat 7", "duration": 138}
]

@app.get("/", tags=["General"])
def home():
    return {
        "message": "Cinema Booking API is running successfully!",
        "version": "1.0.0",
        "docs_url": "/docs"
    }

@app.get("/api/movies", tags=["Movies"])
def get_movies():
    return movies

@app.post("/api/movies", tags=["Movies"])
def create_movie(movie: dict):
    movie["id"] = len(movies) + 1
    movies.append(movie)
    return movie

@app.put("/api/movies/{movie_id}", tags=["Movies"])
def update_movie(movie_id: int, updated_movie: dict):
    for movie in movies:
        if movie["id"] == movie_id:
            movie.update(updated_movie)
            return movie
    return {"message": "Movie not found"}

@app.delete("/api/movies/{movie_id}", tags=["Movies"])
def delete_movie(movie_id: int):
    for movie in movies:
        if movie["id"] == movie_id:
            movies.remove(movie)
            return {"message": "Deleted successfully"}
    return {"message": "Movie not found"}
