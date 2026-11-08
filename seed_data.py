import os
import sys
from datetime import datetime, date, timedelta
from decimal import Decimal

# Cấu hình UTF-8 cho console Windows tránh UnicodeEncodeError
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Thêm thư mục gốc dự án vào sys.path để import app.models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, SessionLocal, Base
import app.models
from app.models import Role, User, Genre, Movie, Cinema, Room, Seat, Showtime
from app.core.security import get_password_hash


def init_database():
    """Tạo tất cả các bảng CSDL nếu chưa tồn tại"""
    print("==================================================================")
    print("CINEMA BOOKING SYSTEM - KHOI TAO BANG & SEED DU LIEU MAU 7 NGAY")
    print("==================================================================")
    print("--> 1. Dang kiem tra va tao cac bang CSDL...")
    Base.metadata.create_all(bind=engine)
    print("    [OK] Da tao toan bo cac bang thanh cong!")


def seed_roles(db):
    """1. Seed danh mục Vai trò (Roles)"""
    print("\n--> 2. Dang kiem tra va seed danh muc Vai tro (Roles)...")
    roles_data = [
        {"id": 1, "name": "ADMIN", "description": "Quan tri vien toan quyen he thong"},
        {"id": 2, "name": "USER", "description": "Khach hang mua ve xem phim truc tuyen"},
    ]
    for r in roles_data:
        existing = db.query(Role).filter(Role.id == r["id"]).first()
        if not existing:
            db.add(Role(**r))
            print(f"    + Da them vai tro: {r['name']}")
    db.commit()
    print("    [OK] Hoan thanh seed Roles.")


def seed_users(db):
    """2. Seed tài khoản Quản trị viên (Admin) và Khách hàng mẫu"""
    print("\n--> 3. Dang kiem tra va seed tai khoan Admin & Khach hang...")
    users_data = [
        {
            "role_id": 1,
            "full_name": "Quan Tri Vien He Thong",
            "email": "admin@cinema.com",
            "phone": "0901234567",
            "password_hash": get_password_hash("admin123"),
            "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb",
            "is_active": True,
        },
        {
            "role_id": 1,
            "full_name": "Le Van Hung (Admin Quan Ly)",
            "email": "hung.le@cinema.com",
            "phone": "0912345678",
            "password_hash": get_password_hash("admin123"),
            "avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d",
            "is_active": True,
        },
        {
            "role_id": 2,
            "full_name": "Nguyen Van Khach Hang",
            "email": "customer@cinema.com",
            "phone": "0987654321",
            "password_hash": get_password_hash("user123"),
            "avatar": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e",
            "is_active": True,
        },
        {
            "role_id": 2,
            "full_name": "Tran Thi Lan",
            "email": "lan.tran@cinema.com",
            "phone": "0978901234",
            "password_hash": get_password_hash("user123"),
            "avatar": "https://images.unsplash.com/photo-1494790108377-be9c29b29330",
            "is_active": True,
        },
    ]

    for u in users_data:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if not existing:
            db.add(User(**u))
            print(f"    + Da tao tai khoan: {u['email']} | Role: {'ADMIN' if u['role_id']==1 else 'USER'}")
    db.commit()
    print("    [OK] Hoan thanh seed Nguoi dung.")


def seed_genres(db):
    """3. Seed danh mục thể loại phim"""
    print("\n--> 4. Dang kiem tra va seed The loai phim (Genres)...")
    genres_data = [
        {"name": "Hanh Dong", "description": "Phim co tiet tau nhanh, ky xao man nhan va canh chien dau."},
        {"name": "Hai Huoc", "description": "Phim dem lai tieng cuoi vui ve va tinh giai tri cao."},
        {"name": "Tinh Cam", "description": "Cau chuyen tinh yeu lang man, sau lang va cam xuc."},
        {"name": "Tam Ly - Gia Dinh", "description": "Khai thac sau sac tam ly con nguoi va cac moi quan he gia dinh."},
        {"name": "Kinh Di", "description": "Gay can, rung ron, kham pha bi an tam linh."},
        {"name": "Khoa Hoc Vien Tuong", "description": "Du hanh khong gian, cong nghe tuong lai."},
        {"name": "Hoat Hinh", "description": "Do hoa dac sac phu hop cho moi lua tuoi gia dinh."},
    ]
    for g in genres_data:
        existing = db.query(Genre).filter(Genre.name == g["name"]).first()
        if not existing:
            db.add(Genre(**g))
            print(f"    + Da them the loai: {g['name']}")
    db.commit()
    print("    [OK] Hoan thanh seed The loai.")


def seed_movies(db):
    """4. Seed danh sách phim và gán thể loại"""
    print("\n--> 5. Dang kiem tra va seed Danh sach phim (Movies)...")
    movies_data = [
        {
            "title": "Mai",
            "slug": "mai-2024",
            "description": "Cau chuyen tinh cam sau sac, nhieu bien co xoay quanh cuoc doi cua Mai va Duong.",
            "duration_minutes": 131,
            "release_date": date(2024, 2, 10),
            "poster_url": "https://upload.wikimedia.org/wikipedia/vi/4/47/Mai_poster.jpg",
            "trailer_url": "https://www.youtube.com/watch?v=0wQv7n38h6g",
            "status": "NOW_SHOWING",
            "genres": ["Tinh Cam", "Tam Ly - Gia Dinh"]
        },
        {
            "title": "Lat Mat 7: Mot Dieu Uoc",
            "slug": "lat-mat-7-mot-dieu-uoc",
            "description": "Bo phim gia dinh xuc dong ve tinh mau tu thieng lieng cua ba Hai 73 tuoi.",
            "duration_minutes": 138,
            "release_date": date(2024, 4, 26),
            "poster_url": "https://upload.wikimedia.org/wikipedia/vi/0/05/Lat_Mat_7_poster.jpg",
            "trailer_url": "https://www.youtube.com/watch?v=8RjQzQ2Q_54",
            "status": "NOW_SHOWING",
            "genres": ["Tam Ly - Gia Dinh", "Hai Huoc"]
        },
        {
            "title": "Dune: Hanh Tinh Cat 2",
            "slug": "dune-part-two",
            "description": "Paul Atreides lien minh cung Chani va nguoi Fremen tren hanh trinh bao thu dinh menh.",
            "duration_minutes": 166,
            "release_date": date(2024, 3, 1),
            "poster_url": "https://image.tmdb.org/t/p/original/8b8R8l88Qje9dn9OE8PY05Nxl1X.jpg",
            "trailer_url": "https://www.youtube.com/watch?v=Way9Dexny3w",
            "status": "NOW_SHOWING",
            "genres": ["Khoa Hoc Vien Tuong", "Hanh Dong"]
        },
        {
            "title": "Quat Mo Trung Ma (Exhuma)",
            "slug": "exhuma-quat-mo-trung-ma",
            "description": "Hai phap su va thay phong thuy khai quat ngoi mo bi an giai cuu gia toc giau co.",
            "duration_minutes": 134,
            "release_date": date(2024, 3, 15),
            "poster_url": "https://image.tmdb.org/t/p/original/tMefBSflR6PGQLv7WvFPpKLZkyk.jpg",
            "trailer_url": "https://www.youtube.com/watch?v=33K_L5e22k4",
            "status": "NOW_SHOWING",
            "genres": ["Kinh Di"]
        },
        {
            "title": "Godzilla x Kong: De Che Moi",
            "slug": "godzilla-x-kong-the-new-empire",
            "description": "Tran chien dinh cao giua Godzilla va Kong chong lai moi de doa an sau trong Trai Dat.",
            "duration_minutes": 115,
            "release_date": date(2024, 3, 29),
            "poster_url": "https://image.tmdb.org/t/p/original/bQ2ywkchCe02AcSnMuVeZ2QIDe.jpg",
            "trailer_url": "https://www.youtube.com/watch?v=lV1OOlGwExg",
            "status": "NOW_SHOWING",
            "genres": ["Hanh Dong", "Khoa Hoc Vien Tuong"]
        },
        {
            "title": "Kung Fu Panda 4",
            "slug": "kung-fu-panda-4",
            "description": "Po tro thanh Thu linh Tinh than cua Thung lung Binh Yen va tim kiem Than Long Dai Hiep moi.",
            "duration_minutes": 94,
            "release_date": date(2024, 3, 8),
            "poster_url": "https://image.tmdb.org/t/p/original/kDp1vUBnMpe8ak4rjgl3cLELqjU.jpg",
            "trailer_url": "https://www.youtube.com/watch?v=_inKs4eeHiI",
            "status": "NOW_SHOWING",
            "genres": ["Hoat Hinh", "Hai Huoc", "Hanh Dong"]
        },
        {
            "title": "Conan: Ngoi Sao 5 Canh 1 Trieu Do",
            "slug": "conan-ngoi-sao-5-canh-1-trieu-do",
            "description": "Cuoc ruot duoi tranh doat thanh kiem giua Sieu dao chich Kid, Hattori va Conan.",
            "duration_minutes": 110,
            "release_date": date.today() + timedelta(days=14),
            "poster_url": "https://image.tmdb.org/t/p/original/7kAC1R8gE7o9U9zW3l3Z5Y2mB1.jpg",
            "trailer_url": "https://www.youtube.com/watch?v=conan_trailer",
            "status": "COMING_SOON",
            "genres": ["Hoat Hinh", "Hanh Dong"]
        }
    ]

    for m_info in movies_data:
        existing = db.query(Movie).filter(Movie.slug == m_info["slug"]).first()
        if not existing:
            genre_names = m_info.pop("genres")
            movie = Movie(**m_info)
            for g_name in genre_names:
                g_obj = db.query(Genre).filter(Genre.name == g_name).first()
                if g_obj:
                    movie.genres.append(g_obj)
            db.add(movie)
            print(f"    + Da them phim: {m_info['title']} ({m_info['duration_minutes']} phut) - {m_info['status']}")
    db.commit()
    print("    [OK] Hoan thanh seed Phim.")


def seed_cinemas_and_rooms(db):
    """5. Seed Cụm Rạp, Phòng chiếu và Ma trận Ghế ngồi"""
    print("\n--> 6. Dang kiem tra va seed Rap (Cinemas), Phong (Rooms) & Ghe (Seats)...")
    cinemas_data = [
        {
            "name": "CGV Vincom Center Ba Trieu",
            "address": "Tang 6, Vincom Center, 191 Ba Trieu, Hai Ba Trung",
            "city": "Ha Noi",
            "phone": "1900 6017",
            "rooms": [
                {"name": "Phong Cinema 01 (Standard)", "room_type": "2D", "rows": 6, "cols": 10},
                {"name": "Phong Cinema 02 (IMAX Laser)", "room_type": "IMAX", "rows": 8, "cols": 12},
                {"name": "Phong Cinema 03 (Gold Class)", "room_type": "VIP", "rows": 4, "cols": 8},
            ]
        },
        {
            "name": "CGV Landmark 81",
            "address": "Tang B1, TTTM Vincom Center Landmark 81, 720A Dien Bien Phu, Binh Thanh",
            "city": "TP. Ho Chi Minh",
            "phone": "1900 6017",
            "rooms": [
                {"name": "Phong 01 (IMAX Laser)", "room_type": "IMAX", "rows": 8, "cols": 12},
                {"name": "Phong 02 (2D Dolby)", "room_type": "2D", "rows": 6, "cols": 10},
            ]
        },
        {
            "name": "Lotte Cinema Keangnam",
            "address": "Tang 5, Keangnam Landmark Tower, Pham Hung, Nam Tu Liem",
            "city": "Ha Noi",
            "phone": "024 3837 8032",
            "rooms": [
                {"name": "Phong Chieu 1", "room_type": "2D", "rows": 6, "cols": 10},
                {"name": "Phong Chieu 2 (3D RealD)", "room_type": "3D", "rows": 6, "cols": 10},
            ]
        },
        {
            "name": "Galaxy Cinema Nguyen Du",
            "address": "116 Nguyen Du, Phuong Ben Thanh, Quan 1",
            "city": "TP. Ho Chi Minh",
            "phone": "1900 2224",
            "rooms": [
                {"name": "Screen 01", "room_type": "2D", "rows": 6, "cols": 10},
                {"name": "Screen 02", "room_type": "2D", "rows": 6, "cols": 10},
            ]
        }
    ]

    total_seats_created = 0

    for c_info in cinemas_data:
        rooms_info = c_info.pop("rooms")
        cinema = db.query(Cinema).filter(Cinema.name == c_info["name"]).first()
        if not cinema:
            cinema = Cinema(**c_info)
            db.add(cinema)
            db.flush()
            print(f"    + Da them rap: {cinema.name} - {cinema.city}")

        for r_info in rooms_info:
            room = db.query(Room).filter(Room.cinema_id == cinema.id, Room.name == r_info["name"]).first()
            rows = r_info["rows"]
            cols = r_info["cols"]
            calc_total_seats = rows * cols

            if not room:
                room = Room(
                    cinema_id=cinema.id,
                    name=r_info["name"],
                    room_type=r_info["room_type"],
                    total_seats=calc_total_seats
                )
                db.add(room)
                db.flush()
                print(f"      - Phong: {room.name} ({room.room_type}) - Quy mo: {calc_total_seats} ghe")

                row_letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
                for r_idx in range(rows):
                    row_char = row_letters[r_idx]
                    for c_idx in range(1, cols + 1):
                        seat_num = f"{row_char}{c_idx:02d}"
                        if r_idx < rows - 3:
                            seat_type = "STANDARD"
                        elif r_idx < rows - 1:
                            seat_type = "VIP"
                        else:
                            seat_type = "COUPLE"

                        seat = Seat(
                            room_id=room.id,
                            seat_number=seat_num,
                            seat_type=seat_type
                        )
                        db.add(seat)
                        total_seats_created += 1

    db.commit()
    print(f"    [OK] Hoan thanh seed Rap, Phong & da tao {total_seats_created} Ghe ngoi.")


def seed_showtimes_7days(db):
    """6. Seed Suất chiếu MẪU CHO 7 NGÀY LIÊN TIẾP (Tính từ ngày chạy script)"""
    print("\n--> 7. Dang kiem tra va seed Suat chieu mau cho 7 NGAY LIEN TIEP...")
    
    movies = db.query(Movie).filter(Movie.status == "NOW_SHOWING").all()
    if not movies:
        print("    [!] Chua co phim dang chieu de tao suat chieu!")
        return

    rooms = db.query(Room).all()
    if not rooms:
        print("    [!] Chua co phong chieu de tao suat chieu!")
        return

    today = date.today()
    showtime_slots = [
        {"start_hour": 9,  "start_min": 0,  "base_price": 75000},
        {"start_hour": 12, "start_min": 0,  "base_price": 85000},
        {"start_hour": 15, "start_min": 0,  "base_price": 95000},
        {"start_hour": 18, "start_min": 15, "base_price": 110000},
        {"start_hour": 21, "start_min": 30, "base_price": 90000},
    ]

    total_showtimes_created = 0
    movie_count = len(movies)

    for day_offset in range(7):
        current_date = today + timedelta(days=day_offset)
        day_label = f"Ngay {day_offset + 1}/7 ({current_date.strftime('%d/%m/%Y')})"
        day_created = 0

        for r_idx, room in enumerate(rooms):
            movie = movies[(r_idx + day_offset) % movie_count]

            for slot_idx, slot in enumerate(showtime_slots):
                if (r_idx + slot_idx) % 2 == 0:
                    start_dt = datetime(
                        current_date.year, current_date.month, current_date.day,
                        slot["start_hour"], slot["start_min"], 0
                    )
                    end_dt = start_dt + timedelta(minutes=movie.duration_minutes + 15)

                    price = slot["base_price"]
                    if room.room_type == "IMAX":
                        price = int(price * 1.5)
                    elif room.room_type == "VIP":
                        price = int(price * 1.3)

                    existing_st = db.query(Showtime).filter(
                        Showtime.room_id == room.id,
                        Showtime.start_time == start_dt
                    ).first()

                    if not existing_st:
                        showtime = Showtime(
                            movie_id=movie.id,
                            room_id=room.id,
                            start_time=start_dt,
                            end_time=end_dt,
                            price=Decimal(price)
                        )
                        db.add(showtime)
                        total_showtimes_created += 1
                        day_created += 1

        print(f"    + {day_label}: Da tao {day_created} suat chieu.")

    db.commit()
    print(f"    [OK] Hoan thanh seed {total_showtimes_created} Suat chieu cho ca 7 ngay!")


def main():
    try:
        init_database()
        db = SessionLocal()
        try:
            seed_roles(db)
            seed_users(db)
            seed_genres(db)
            seed_movies(db)
            seed_cinemas_and_rooms(db)
            seed_showtimes_7days(db)
            print("\n==================================================================")
            print("SEED TOAN BO DU LIEU MAU CHO CA NHOM THANH CONG!")
            print("==================================================================")
            print("TAI KHOAN TEST CHO NHOM:")
            print("   - Admin:    admin@cinema.com    | Mat khau: admin123 (Toan quyen he thong)")
            print("   - Admin 2:  hung.le@cinema.com  | Mat khau: admin123 (Le Van Hung)")
            print("   - Khach:    customer@cinema.com | Mat khau: user123  (Dat ve xem phim)")
            print("==================================================================")
        finally:
            db.close()
    except Exception as e:
        print(f"\n[LOI SEED CSDL]: {e}")
        print("\nGOI Y KHAC PHUC:")
        print("1. Kiem tra MySQL Server da chay va database 'cinema_booking_system_db' da duoc tao.")
        print("2. Hoac kiem tra mat khau root MySQL trong file .env hoac database.py.")


if __name__ == "__main__":
    main()
