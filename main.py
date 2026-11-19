import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import movies, auth, admin, seats, showtimes, cinemas, rooms, bookings, users, payments

app = FastAPI(
    title="Cinema Booking System API",
    description="Hệ thống Backend Đặt vé xem phim trực tuyến - Tích hợp Admin Portal & Security",
    version="1.0.0"
)

# Cấu hình CORS cho Frontend kết nối
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép mọi origin của FE
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tạo và Mount thư mục tĩnh /uploads phục vụ ảnh poster, avatar (SRS 1.2)
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "app", "uploads")
os.makedirs(os.path.join(UPLOAD_DIR, "posters"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "avatars"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Đăng ký các router vào hệ thống
app.include_router(movies.router)
app.include_router(auth.router)
app.include_router(auth.router, prefix="/api/auth", include_in_schema=False)  # Alias tương thích
app.include_router(admin.router, prefix="/api/admin")
app.include_router(admin.router, prefix="/admin", include_in_schema=False)  # Alias tương thích
app.include_router(seats.router)
app.include_router(showtimes.router)
app.include_router(cinemas.router)
app.include_router(rooms.router)
app.include_router(bookings.router)
app.include_router(payments.router)
app.include_router(users.router)

@app.get("/", tags=["Root"])
def home():
    return {
        "message": "Cinema Booking API is running successfully",
        "version": "1.0.0",
        "docs_url": "/docs"
    }
