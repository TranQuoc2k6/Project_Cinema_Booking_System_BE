from database import engine, SessionLocal, Base
import app.models  # Import package models để SQLAlchemy nhận diện tất cả bảng


def create_tables_and_seed_data():
    print("--> Đang khởi tạo các bảng trong cơ sở dữ liệu MySQL...")
    # Lệnh tự động tạo tất cả các bảng đã định nghĩa trong app/models/
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Chèn dữ liệu vai trò ban đầu nếu chưa có
        initial_roles = [
            {"id": 1, "name": "ADMIN", "description": "Quản trị viên toàn quyền hệ thống"},
            {"id": 2, "name": "USER", "description": "Khách hàng mua vé xem phim"}
        ]

        for role_data in initial_roles:
            existing_role = db.query(app.models.Role).filter(app.models.Role.id == role_data["id"]).first()
            if not existing_role:
                new_role = app.models.Role(**role_data)
                db.add(new_role)
                print(f"    + Đã chèn vai trò mặc định: {role_data['name']}")

        db.commit()
        print("--> Khởi tạo bảng và dữ liệu mẫu thành công!")
    except Exception as e:
        db.rollback()
        print(f"--> Lỗi khởi tạo cơ sở dữ liệu: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    create_tables_and_seed_data()