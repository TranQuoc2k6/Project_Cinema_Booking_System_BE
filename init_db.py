
from datetime import date

from database import engine, SessionLocal, Base
import app.models

from app.models import Role, Movie, Genre


def create_tables_and_seed_data():
    print("--> Dang khoi tao cac bang...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # 1. Them vai tro mac dinh
        initial_roles = [
            {"id": 1, "name": "ADMIN", "description": "Quan tri vien"},
            {"id": 2, "name": "USER", "description": "Khach hang"}
        ]

        for role_data in initial_roles:
            existing_role = db.query(Role).filter(
                Role.id == role_data["id"]
            ).first()

            if not existing_role:
                db.add(Role(**role_data))

        # 2. Them the loai phim
        genre_names = [
            "Hanh dong",
            "Tinh cam",
            "Hai",
            "Kinh di",
            "Hoat hinh",
            "Vien tuong",
            "Tam ly",
            "Phieu luu"
        ]

        genres = {}

        for name in genre_names:
            genre = db.query(Genre).filter(Genre.name == name).first()

            if not genre:
                genre = Genre(name=name)
                db.add(genre)

            genres[name] = genre

        db.flush()

        # 3. Them 15 phim mau
        movies_data = [
            {
                "title": "Mai",
                "description": "Cau chuyen ve cuoc doi va tinh yeu cua Mai.",
                "duration": 131,
                "release_date": date(2024, 2, 10),
                "poster": None,
                "trailer": None,
                "age_rating": "T16",
                "status": "ENDED",
                "genres": ["Tinh cam", "Tam ly"]
            },
            {
                "title": "Lat Mat 7: Mot Dieu Uoc",
                "description": "Cau chuyen ve tinh cam gia dinh.",
                "duration": 138,
                "release_date": date(2024, 4, 26),
                "poster": None,
                "trailer": None,
                "age_rating": "T13",
                "status": "ENDED",
                "genres": ["Tam ly", "Tinh cam"]
            },
            {
                "title": "Bo Tu Bao Thu",
                "description": "Bo phim hai ve tinh ban va gia dinh.",
                "duration": 138,
                "release_date": date(2025, 1, 29),
                "poster": None,
                "trailer": None,
                "age_rating": "T13",
                "status": "ENDED",
                "genres": ["Hai", "Tinh cam"]
            },
            {
                "title": "Nha Ba Nu",
                "description": "Cau chuyen ve mau thuan trong gia dinh.",
                "duration": 102,
                "release_date": date(2023, 1, 22),
                "poster": None,
                "trailer": None,
                "age_rating": "T18",
                "status": "ENDED",
                "genres": ["Tam ly", "Hai"]
            },
            {
                "title": "Doraemon: Nobita va Ban Giao Huong Dia Cau",
                "description": "Chuyen phieu luu cua Doraemon va Nobita.",
                "duration": 115,
                "release_date": date(2024, 5, 24),
                "poster": None,
                "trailer": None,
                "age_rating": "P",
                "status": "ENDED",
                "genres": ["Hoat hinh", "Phieu luu"]
            },
            {
                "title": "Inside Out 2",
                "description": "Hanh trinh kham pha cam xuc cua Riley.",
                "duration": 96,
                "release_date": date(2024, 6, 14),
                "poster": None,
                "trailer": None,
                "age_rating": "P",
                "status": "ENDED",
                "genres": ["Hoat hinh", "Hai"]
            },
            {
                "title": "Deadpool & Wolverine",
                "description": "Cuoc phieu luu cua Deadpool va Wolverine.",
                "duration": 128,
                "release_date": date(2024, 7, 26),
                "poster": None,
                "trailer": None,
                "age_rating": "T18",
                "status": "ENDED",
                "genres": ["Hanh dong", "Hai"]
            },
            {
                "title": "Venom: The Last Dance",
                "description": "Cuoc chien cuoi cung cua Venom.",
                "duration": 109,
                "release_date": date(2024, 10, 25),
                "poster": None,
                "trailer": None,
                "age_rating": "T16",
                "status": "ENDED",
                "genres": ["Hanh dong", "Vien tuong"]
            },
            {
                "title": "Moana 2",
                "description": "Moana tiep tuc hanh trinh tren dai duong.",
                "duration": 100,
                "release_date": date(2024, 11, 27),
                "poster": None,
                "trailer": None,
                "age_rating": "P",
                "status": "ENDED",
                "genres": ["Hoat hinh", "Phieu luu"]
            },
            {
                "title": "Mufasa: The Lion King",
                "description": "Cau chuyen ve nguon goc cua Mufasa.",
                "duration": 118,
                "release_date": date(2024, 12, 20),
                "poster": None,
                "trailer": None,
                "age_rating": "P",
                "status": "ENDED",
                "genres": ["Phieu luu", "Hoat hinh"]
            },
            {
                "title": "Captain America: Brave New World",
                "description": "Sam Wilson tiep nhan vai tro Captain America.",
                "duration": 118,
                "release_date": date(2025, 2, 14),
                "poster": None,
                "trailer": None,
                "age_rating": "T13",
                "status": "ENDED",
                "genres": ["Hanh dong", "Vien tuong"]
            },
            {
                "title": "How to Train Your Dragon",
                "description": "Tinh ban giua Hiccup va rong Toothless.",
                "duration": 125,
                "release_date": date(2025, 6, 13),
                "poster": None,
                "trailer": None,
                "age_rating": "P",
                "status": "ENDED",
                "genres": ["Phieu luu", "Hoat hinh"]
            },
            {
                "title": "Avatar: Fire and Ash",
                "description": "Phan tiep theo cua hanh trinh tren Pandora.",
                "duration": 197,
                "release_date": date(2026, 12, 18),
                "poster": None,
                "trailer": None,
                "age_rating": "T13",
                "status": "COMING_SOON",
                "genres": ["Vien tuong", "Phieu luu"]
            },
            {
                "title": "Zootopia 2",
                "description": "Judy va Nick tiep tuc pha an.",
                "duration": 108,
                "release_date": date(2025, 11, 26),
                "poster": None,
                "trailer": None,
                "age_rating": "P",
                "status": "ENDED",
                "genres": ["Hoat hinh", "Hai"]
            },
            {
                "title": "The Conjuring: Last Rites",
                "description": "Vu an sieu nhien moi cua gia dinh Warren.",
                "duration": 135,
                "release_date": date(2025, 9, 5),
                "poster": None,
                "trailer": None,
                "age_rating": "T18",
                "status": "ENDED",
                "genres": ["Kinh di", "Tam ly"]
            }
        ]

        for movie_data in movies_data:
            existing_movie = db.query(Movie).filter(
                Movie.title == movie_data["title"]
            ).first()

            if not existing_movie:
                genre_list = [
                    genres[name] for name in movie_data["genres"]
                ]

                movie_data["genres"] = genre_list
                db.add(Movie(**movie_data))

        db.commit()
        print("--> Seed du lieu thanh cong!")

    except Exception as e:
        db.rollback()
        print(f"--> Loi: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    create_tables_and_seed_data()
