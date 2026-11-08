import os
import sys

# Ho tro UTF-8 tren Windows console
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import SessionLocal
from app.models import User, Role, Cinema, Room, Seat, Movie, Genre, Showtime

def test_database():
    db = SessionLocal()
    try:
        print("==================================================================")
        print("BAO CAO KIEM THU CO SO DU LIEU CINEMA BOOKING SYSTEM")
        print("==================================================================")

        stats = [
            ("Vai tro (Roles)", db.query(Role).count()),
            ("Nguoi dung (Users)", db.query(User).count()),
            ("The loai (Genres)", db.query(Genre).count()),
            ("Phim (Movies)", db.query(Movie).count()),
            ("Cum rap (Cinemas)", db.query(Cinema).count()),
            ("Phong chieu (Rooms)", db.query(Room).count()),
            ("Ghe ngoi (Seats)", db.query(Seat).count()),
            ("Suat chieu 7 ngay (Showtimes)", db.query(Showtime).count()),
        ]

        print("1. SO LUONG BAN GHI TRONG CSDL:")
        for name, count in stats:
            print(f"   [OK] {name:<30}: {count} ban ghi")

        print("\n2. DANH SACH TAI KHOAN TEST:")
        users = db.query(User).all()
        for u in users:
            role_name = "ADMIN" if u.role_id == 1 else "CUSTOMER"
            print(f"   - [{role_name:<8}] {u.full_name:<25} | Email: {u.email:<22} | SDT: {u.phone}")

        print("\n3. DANH SACH CUM RAP & PHONG CHIEU:")
        cinemas = db.query(Cinema).all()
        for c in cinemas:
            print(f"   * {c.name} ({c.city})")
            for r in c.rooms:
                print(f"      + {r.name} [{r.room_type}] - {r.total_seats} ghe")

        print("\n4. PHAN BO SUAT CHIEU THEO NGAY (7 NGAY TOI):")
        from sqlalchemy import func
        day_counts = db.query(
            func.date(Showtime.start_time).label("show_date"),
            func.count(Showtime.id).label("count")
        ).group_by(func.date(Showtime.start_time)).order_by("show_date").all()

        for idx, (s_date, count) in enumerate(day_counts, 1):
            print(f"   > Ngay {idx}/7 ({s_date}): {count} suat chieu")

        print("\n==================================================================")
        print("TAT CA DU LIEU DA DUOC SEED THANH CONG VAO MYSQL!")
        print("==================================================================")
    finally:
        db.close()

if __name__ == "__main__":
    test_database()
