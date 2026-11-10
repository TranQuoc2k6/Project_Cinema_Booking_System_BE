from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import movies, auth, admin

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

# Đăng ký các router vào hệ thống
app.include_router(movies.router)
app.include_router(auth.router)
app.include_router(auth.router, prefix="/api/auth", include_in_schema=False)  # Alias tương thích
app.include_router(admin.router, prefix="/api/admin", tags=["Admin Portal"])


@app.get("/", tags=["Root"])
def home():
    return {
        "message": "Cinema Booking API is running successfully",
        "version": "1.0.0",
        "docs_url": "/docs"
    }
