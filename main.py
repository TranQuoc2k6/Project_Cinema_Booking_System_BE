from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import movies, auth, seats

app = FastAPI(
    title="Cinema Booking System API",
    version="1.0.0"
)

# Cấu hình CORS cho Frontend kết nối
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Hoặc cấu hình domain cụ thể của FE, ví dụ: ["http://localhost:3000", "http://127.0.0.1:5500"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các router vào hệ thống
app.include_router(movies.router)
app.include_router(auth.router)
app.include_router(seats.router)
# app.include_router(showtimes.router)

@app.get("/", tags=["Root"])
def home():
    return {"message": "Cinema Booking API is running"}