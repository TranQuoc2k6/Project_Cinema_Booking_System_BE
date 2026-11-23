import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import SessionLocal
from app.routers import movies, auth, admin, seats, showtimes, cinemas, rooms, bookings, users, payments, tickets, reviews


async def background_daily_showtime_maintenance():
    """
    Tác vụ chạy ngầm định kỳ:
    - Khi hết ngày / sang ngày mới: dọn dẹp các suất chiếu cũ của ngày hôm trước
    - Tự động sinh suất chiếu cho 7 ngày tiếp theo để luôn duy trì lịch chiếu liên tục
    """
    while True:
        try:
            # Chờ 1 giờ trước mỗi lần quét định kỳ
            await asyncio.sleep(3600)
            db = SessionLocal()
            try:
                from app.services.showtime_service import cleanup_past_showtimes, auto_generate_showtimes
                cleanup_past_showtimes(db)
                auto_generate_showtimes(db, days_ahead=7)
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Periodic Showtime Maintenance Error] {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động: chạy dọn dẹp và tự động sinh suất chiếu ngay khi khởi động server
    try:
        db = SessionLocal()
        try:
            from app.services.showtime_service import cleanup_past_showtimes, auto_generate_showtimes
            cleanup_past_showtimes(db)
            auto_generate_showtimes(db, days_ahead=7)
        finally:
            db.close()
    except Exception as e:
        print(f"[Startup Showtime Maintenance Notice] {e}")

    # Bắt đầu vòng lặp chạy ngầm
    maintenance_task = asyncio.create_task(background_daily_showtime_maintenance())
    yield
    maintenance_task.cancel()
    try:
        await maintenance_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Cinema Booking System API",
    description="Hệ thống Backend Đặt vé xem phim trực tuyến - Tích hợp Admin Portal & Security",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(tickets.router)
app.include_router(payments.router)
app.include_router(users.router)
app.include_router(reviews.router)

@app.get("/", tags=["Root"])
def home():
    return {
        "message": "Cinema Booking API is running successfully",
        "version": "1.0.0",
        "docs_url": "/docs"
    }
