import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.models.role import Role
from app.models.user import User
from app.models.genre import Genre
from app.models.movie import Movie
from main import app

# In-memory SQLite for isolated, lightning-fast tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestAdminMoviesAPI(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        db = TestingSessionLocal()

        # 1. Seed Roles
        admin_role = Role(id=1, name="ADMIN", description="Quản trị viên")
        customer_role = Role(id=2, name="USER", description="Khách hàng")
        db.add_all([admin_role, customer_role])
        db.commit()

        # 2. Seed Users
        admin_user = User(
            id=1,
            role_id=1,
            full_name="Admin Master",
            email="admin@cinema.com",
            password_hash=hash_password("admin123"),
            is_active=True
        )
        customer_user = User(
            id=2,
            role_id=2,
            full_name="Nguyen Van A",
            email="user@cinema.com",
            password_hash=hash_password("user123"),
            is_active=True
        )
        db.add_all([admin_user, customer_user])
        db.commit()

        # 3. Seed Genres
        g1 = Genre(id=1, name="Hành động", description="Phim hành động kịch tính")
        g2 = Genre(id=2, name="Khoa học viễn tưởng", description="Phim Sci-Fi")
        g3 = Genre(id=3, name="Tâm lý", description="Phim tâm lý tình cảm")
        db.add_all([g1, g2, g3])
        db.commit()

        # 4. Seed 1 Movie mẫu
        m1 = Movie(
            id=1,
            title="Mai (18+)",
            slug="mai-18",
            description="Tác phẩm tâm lý tình cảm của Trấn Thành",
            duration_minutes=131,
            release_date=date(2026, 2, 10),
            poster_url="https://example.com/mai.jpg",
            status="NOW_SHOWING",
            genres=[g1, g3]
        )
        db.add(m1)
        db.commit()
        db.close()

        # Generate tokens
        self.admin_token = create_access_token(data={"sub": "1", "email": "admin@cinema.com"})
        self.customer_token = create_access_token(data={"sub": "2", "email": "user@cinema.com"})
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.customer_headers = {"Authorization": f"Bearer {self.customer_token}"}

    def tearDown(self):
        Base.metadata.drop_all(bind=engine)

    # ------------------------------------------------------------------------
    # 1. KIỂM THỬ BẢO MẬT & PHÂN QUYỀN (REQUIRE_ADMIN GUARD)
    # ------------------------------------------------------------------------

    def test_admin_movies_no_token_returns_401(self):
        """Không truyền token -> phải chặn 401 Unauthorized"""
        res = client.get("/admin/movies")
        self.assertEqual(res.status_code, 401)
        self.assertIn("Bearer", res.headers.get("www-authenticate", ""))

    def test_admin_movies_customer_token_returns_403(self):
        """Khách hàng (role USER) gọi API admin -> phải chặn 403 Forbidden"""
        res = client.get("/admin/movies", headers=self.customer_headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("không có quyền", res.json().get("detail", ""))

    # ------------------------------------------------------------------------
    # 2. KIỂM THỬ THÊM PHIM & GÁN THỂ LOẠI (POST /admin/movies)
    # ------------------------------------------------------------------------

    def test_create_movie_success(self):
        """Thêm phim mới thành công với thời lượng, ngày khởi chiếu và gán thể loại"""
        payload = {
            "title": "Dune: Hành Tinh Cát 2",
            "duration_minutes": 166,
            "release_date": "2026-03-01",
            "description": "Cuộc chiến trên sa mạc Arrakis",
            "poster_url": "https://example.com/dune2.jpg",
            "trailer_url": "https://youtube.com/dune2",
            "status": "now_showing",
            "genre_ids": [1, 2]  # Hành động, Khoa học viễn tưởng
        }
        res = client.post("/admin/movies", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["title"], "Dune: Hành Tinh Cát 2")
        self.assertEqual(data["duration_minutes"], 166)
        self.assertEqual(data["release_date"], "2026-03-01")
        self.assertEqual(data["status"], "now_showing")
        self.assertEqual(len(data["genres"]), 2)
        genre_names = [g["name"] for g in data["genres"]]
        self.assertIn("Hành động", genre_names)
        self.assertIn("Khoa học viễn tưởng", genre_names)

    def test_create_movie_alias_endpoint(self):
        """Kiểm tra endpoint alias /api/admin/movies cũng hoạt động chuẩn xác"""
        payload = {
            "title": "Godzilla x Kong",
            "duration": 115,
            "release_date": "2026-04-12",
            "genre_ids": [1]
        }
        res = client.post("/api/admin/movies", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["title"], "Godzilla x Kong")
        self.assertEqual(res.json()["duration_minutes"], 115)

    def test_create_movie_validate_duration_zero_or_negative(self):
        """Thời lượng phim <= 0 phải bị từ chối với lỗi 400 hoặc 422 rõ ràng"""
        payload = {
            "title": "Phim Lỗi Thời Lượng",
            "duration_minutes": 0,
            "release_date": "2026-05-01",
            "genre_ids": [1]
        }
        res = client.post("/admin/movies", json=payload, headers=self.admin_headers)
        self.assertIn(res.status_code, [400, 422])

        payload_neg = {
            "title": "Phim Lỗi Thời Lượng Âm",
            "duration_minutes": -45,
            "release_date": "2026-05-01"
        }
        res_neg = client.post("/admin/movies", json=payload_neg, headers=self.admin_headers)
        self.assertIn(res_neg.status_code, [400, 422])

    def test_create_movie_validate_missing_release_date(self):
        """Thiếu ngày khởi chiếu phải bị từ chối"""
        payload = {
            "title": "Phim Thiếu Ngày",
            "duration_minutes": 120
        }
        res = client.post("/admin/movies", json=payload, headers=self.admin_headers)
        self.assertIn(res.status_code, [400, 422])

    def test_create_movie_validate_empty_title(self):
        """Tên phim rỗng hoặc chỉ có khoảng trắng phải bị từ chối"""
        payload = {
            "title": "   ",
            "duration_minutes": 100,
            "release_date": "2026-06-01"
        }
        res = client.post("/admin/movies", json=payload, headers=self.admin_headers)
        self.assertIn(res.status_code, [400, 422])

    def test_create_movie_validate_invalid_genre_ids(self):
        """Gán thể loại không tồn tại trong hệ thống phải trả lỗi 400 Bad Request"""
        payload = {
            "title": "Phim Thể Loại Ảo",
            "duration_minutes": 100,
            "release_date": "2026-06-01",
            "genre_ids": [9999]
        }
        res = client.post("/admin/movies", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("không tồn tại", res.json()["detail"])

    # ------------------------------------------------------------------------
    # 3. KIỂM THỬ SỬA PHIM & CẬP NHẬT THỂ LOẠI (PUT / PATCH /admin/movies/{id})
    # ------------------------------------------------------------------------

    def test_update_movie_success(self):
        """Chỉnh sửa thông tin phim và thay đổi danh sách thể loại thành công"""
        payload = {
            "title": "Mai: Bản Đặc Biệt",
            "duration_minutes": 140,
            "release_date": "2026-02-14",
            "genre_ids": [2, 3]  # Đổi sang Sci-Fi và Tâm lý
        }
        res = client.put("/admin/movies/1", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["title"], "Mai: Bản Đặc Biệt")
        self.assertEqual(data["duration_minutes"], 140)
        self.assertEqual(data["release_date"], "2026-02-14")
        genre_ids = [g["id"] for g in data["genres"]]
        self.assertIn(2, genre_ids)
        self.assertIn(3, genre_ids)
        self.assertNotIn(1, genre_ids)

    def test_update_movie_duration_validation(self):
        """Sửa thời lượng thành số <= 0 phải bị từ chối"""
        payload = {"duration_minutes": -10}
        res = client.put("/admin/movies/1", json=payload, headers=self.admin_headers)
        self.assertIn(res.status_code, [400, 422])

    def test_update_movie_invalid_genre_ids(self):
        """Sửa thể loại thành ID không tồn tại phải báo 400"""
        payload = {"genre_ids": [8888]}
        res = client.patch("/admin/movies/1", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 400)

    def test_update_movie_not_found(self):
        """Sửa phim có ID không tồn tại phải trả 404"""
        res = client.put("/admin/movies/9999", json={"title": "Test"}, headers=self.admin_headers)
        self.assertEqual(res.status_code, 404)

    # ------------------------------------------------------------------------
    # 4. KIỂM THỬ NGỪNG CHIẾU PHIM (PATCH & POST /admin/movies/{id}/stop)
    # ------------------------------------------------------------------------

    def test_stop_movie_success_patch(self):
        """Ngừng chiếu phim qua PATCH /admin/movies/{id}/stop"""
        res = client.patch("/admin/movies/1/stop", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["movie_status"], "ended")
        self.assertIn("ngừng chiếu", body["message"].lower())

        # Kiểm tra lại qua GET chi tiết
        get_res = client.get("/admin/movies/1", headers=self.admin_headers)
        self.assertEqual(get_res.json()["status"], "ended")

    def test_stop_movie_success_post_alias(self):
        """Ngừng chiếu phim qua POST alias /admin/movies/{id}/stop"""
        res = client.post("/admin/movies/1/stop", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["movie_status"], "ended")

    def test_stop_movie_not_found(self):
        """Ngừng chiếu phim không tồn tại -> 404 Not Found"""
        res = client.patch("/admin/movies/9999/stop", headers=self.admin_headers)
        self.assertEqual(res.status_code, 404)

    # ------------------------------------------------------------------------
    # 5. KIỂM THỬ CẬP NHẬT TRẠNG THÁI (PATCH /admin/movies/{id}/status)
    # ------------------------------------------------------------------------

    def test_update_movie_status_success(self):
        """Cập nhật trạng thái phim linh hoạt sang coming_soon hoặc now_showing"""
        res = client.patch(
            "/admin/movies/1/status",
            json={"status": "coming_soon"},
            headers=self.admin_headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["movie_status"], "coming_soon")

    def test_update_movie_status_invalid(self):
        """Trạng thái không hợp lệ phải bị chặn"""
        res = client.patch(
            "/admin/movies/1/status",
            json={"status": "invalid_status_xyz"},
            headers=self.admin_headers
        )
        self.assertIn(res.status_code, [400, 422])

    # ------------------------------------------------------------------------
    # 6. KIỂM THỬ DANH SÁCH & CHI TIẾT & XÓA (GET & DELETE /admin/movies)
    # ------------------------------------------------------------------------

    def test_get_admin_movies_list(self):
        """Lấy danh sách phim cho Admin kèm phân trang"""
        res = client.get("/admin/movies?page=1&limit=10", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["total"] >= 1)
        self.assertTrue(len(body["items"]) >= 1)
        first_movie = body["items"][0]
        self.assertIn("genres", first_movie)
        self.assertIn("duration_minutes", first_movie)

    def test_get_admin_movie_detail(self):
        """Lấy chi tiết 1 phim theo ID"""
        res = client.get("/admin/movies/1", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["id"], 1)

    def test_delete_movie(self):
        """Xóa phim khỏi hệ thống"""
        res = client.delete("/admin/movies/1", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

        # Kiểm tra lại đã bị xóa
        get_res = client.get("/admin/movies/1", headers=self.admin_headers)
        self.assertEqual(get_res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
