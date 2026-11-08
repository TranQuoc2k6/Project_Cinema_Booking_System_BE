"""
Khởi tạo bảng và nạp dữ liệu mẫu cho toàn bộ hệ thống Cinema Booking System.
Hỗ trợ seed Tài khoản Admin, Rạp, Phòng chiếu, Ghế và Suất chiếu 7 ngày cho cả nhóm test chung.
"""
from database import engine, SessionLocal, Base
import app.models
from seed_data import (
    seed_roles,
    seed_users,
    seed_genres,
    seed_movies,
    seed_cinemas_and_rooms,
    seed_showtimes_7days
)


def create_tables_and_seed_data():
    print("--> Đang khởi tạo các bảng trong cơ sở dữ liệu...")
    # Lệnh tự động tạo tất cả các bảng đã định nghĩa trong app/models/
    Base.metadata.create_all(bind=engine)
    print("--> Tạo bảng thành công! Đang tiến hành nạp dữ liệu mẫu...")

    db = SessionLocal()
    try:
        seed_roles(db)
        seed_users(db)
        seed_genres(db)
        seed_movies(db)
        seed_cinemas_and_rooms(db)
        seed_showtimes_7days(db)
        print("--> Khởi tạo bảng và toàn bộ dữ liệu mẫu 7 ngày thành công!")
    except Exception as e:
        db.rollback()
        print(f"--> Lỗi khởi tạo cơ sở dữ liệu: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    create_tables_and_seed_data()
