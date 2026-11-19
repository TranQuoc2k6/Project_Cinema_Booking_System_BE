import os
import sys
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.models.role import Role
from app.models.user import User
from app.models.cinema import Cinema
from app.models.room import Room
from app.models.movie import Movie
from app.models.showtime import Showtime
from app.models.booking import Booking
from main import app

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


class TestAdminShowtimesAPI(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        db = TestingSessionLocal()

        # Seed roles
        admin_role = Role(id=1, name="admin")
        customer_role = Role(id=2, name="customer")
        db.add_all([admin_role, customer_role])
        db.commit()

        # Seed users
        self.admin_user = User(
            id=1,
            email="admin@test.com",
            full_name="Admin User",
            password_hash=hash_password("admin123"),
            role_id=1,
            is_active=True,
        )
        self.normal_user = User(
            id=2,
            email="user@test.com",
            full_name="Normal User",
            password_hash=hash_password("user123"),
            role_id=2,
            is_active=True,
        )
        db.add_all([self.admin_user, self.normal_user])
        db.commit()

        # Seed Cinema & Rooms
        self.cinema = Cinema(
            id=1,
            name="CGV Vincom Ba Trieu",
            address="191 Ba Trieu",
            city="Ha Noi",
            phone="19006017",
        )
        db.add(self.cinema)
        db.commit()

        self.room1 = Room(id=1, cinema_id=1, name="Room 01", room_type="2D", total_seats=60)
        self.room2 = Room(id=2, cinema_id=1, name="Room 02", room_type="IMAX", total_seats=96)
        db.add_all([self.room1, self.room2])
        db.commit()

        # Seed Movies
        self.movie1 = Movie(
            id=1,
            title="Mai",
            slug="mai",
            duration_minutes=120,
            release_date=date(2026, 11, 10),
            status="now_showing",
        )
        self.movie2 = Movie(
            id=2,
            title="Dune 2",
            slug="dune-2",
            duration_minutes=150,
            release_date=date(2026, 11, 10),
            status="now_showing",
        )
        db.add_all([self.movie1, self.movie2])
        db.commit()

        # Generate tokens before closing db
        self.admin_id = self.admin_user.id
        self.normal_user_id = self.normal_user.id

        self.admin_token = create_access_token(
            data={"sub": str(self.admin_id), "role": "admin"}
        )
        self.user_token = create_access_token(
            data={"sub": str(self.normal_user_id), "role": "customer"}
        )

        db.close()

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.user_headers = {"Authorization": f"Bearer {self.user_token}"}

    def tearDown(self):
        Base.metadata.drop_all(bind=engine)

    def test_create_showtime_success(self):
        start = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        payload = {
            "movie_id": 1,
            "room_id": 1,
            "start_time": start.isoformat(),
            "price": 95000,
        }
        res = client.post("/api/admin/showtimes", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["movie_title"], "Mai")
        self.assertEqual(data["room_name"], "Room 01")
        self.assertEqual(float(data["price"]), 95000.0)

        # End time should be auto-calculated to start + 120 minutes
        expected_end = start + timedelta(minutes=120)
        actual_end = datetime.fromisoformat(data["end_time"])
        self.assertEqual(actual_end, expected_end)

    def test_conflict_same_room_overlap(self):
        start1 = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        payload1 = {
            "movie_id": 1,  # 120 mins -> 10:00 to 12:00
            "room_id": 1,
            "start_time": start1.isoformat(),
            "price": 95000,
        }
        res1 = client.post("/api/admin/showtimes", json=payload1, headers=self.admin_headers)
        self.assertEqual(res1.status_code, 201)

        # Overlapping start time: 11:00 to 13:00 in Room 1
        start2 = (datetime.now() + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
        payload2 = {
            "movie_id": 1,
            "room_id": 1,
            "start_time": start2.isoformat(),
            "price": 95000,
        }
        res2 = client.post("/api/admin/showtimes", json=payload2, headers=self.admin_headers)
        self.assertEqual(res2.status_code, 409)
        self.assertIn("Trùng lịch chiếu", res2.json()["detail"])

    def test_conflict_within_15min_cleaning_buffer_after(self):
        """Showtime 1: 10:00 - 12:00. Cleaning is until 12:15.
        Showtime 2 starting at 12:10 in the same room must be BLOCKED."""
        start1 = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        client.post(
            "/api/admin/showtimes",
            json={"movie_id": 1, "room_id": 1, "start_time": start1.isoformat(), "price": 95000},
            headers=self.admin_headers,
        )

        start2 = (datetime.now() + timedelta(days=1)).replace(hour=12, minute=10, second=0, microsecond=0)
        res = client.post(
            "/api/admin/showtimes",
            json={"movie_id": 1, "room_id": 1, "start_time": start2.isoformat(), "price": 95000},
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 409)
        self.assertIn("15 phút dọn phòng", res.json()["detail"])

    def test_conflict_within_15min_cleaning_buffer_before(self):
        """Showtime 1: 10:00 - 12:00.
        Showtime 2: 07:50 - 09:50 (duration 120 min, valid for movie 1).
        Its cleaning is until 10:05, so it overlaps with Showtime 1 starting at 10:00. Must be BLOCKED with 409."""
        start1 = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        client.post(
            "/api/admin/showtimes",
            json={"movie_id": 1, "room_id": 1, "start_time": start1.isoformat(), "price": 95000},
            headers=self.admin_headers,
        )

        start2 = (datetime.now() + timedelta(days=1)).replace(hour=7, minute=50, second=0, microsecond=0)
        end2 = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=50, second=0, microsecond=0)
        res = client.post(
            "/api/admin/showtimes",
            json={
                "movie_id": 1,
                "room_id": 1,
                "start_time": start2.isoformat(),
                "end_time": end2.isoformat(),
                "price": 95000,
            },
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 409)
        self.assertIn("15 phút dọn phòng", res.json()["detail"])

    def test_adjacent_cleaning_buffer_allowed(self):
        """Showtime 1: 10:00 - 12:00. Cleaning ends exactly at 12:15.
        Showtime 2 starts at 12:15 in the same room. Should be ALLOWED (201)."""
        start1 = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        client.post(
            "/api/admin/showtimes",
            json={"movie_id": 1, "room_id": 1, "start_time": start1.isoformat(), "price": 95000},
            headers=self.admin_headers,
        )

        start2 = (datetime.now() + timedelta(days=1)).replace(hour=12, minute=15, second=0, microsecond=0)
        res = client.post(
            "/api/admin/showtimes",
            json={"movie_id": 1, "room_id": 1, "start_time": start2.isoformat(), "price": 95000},
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 201)

    def test_different_room_allowed(self):
        """Same start time in Room 1 and Room 2 should be ALLOWED."""
        start1 = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        res1 = client.post(
            "/api/admin/showtimes",
            json={"movie_id": 1, "room_id": 1, "start_time": start1.isoformat(), "price": 95000},
            headers=self.admin_headers,
        )
        self.assertEqual(res1.status_code, 201)

        res2 = client.post(
            "/api/admin/showtimes",
            json={"movie_id": 1, "room_id": 2, "start_time": start1.isoformat(), "price": 95000},
            headers=self.admin_headers,
        )
        self.assertEqual(res2.status_code, 201)

    def test_update_showtime(self):
        start = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        res = client.post(
            "/api/admin/showtimes",
            json={"movie_id": 1, "room_id": 1, "start_time": start.isoformat(), "price": 95000},
            headers=self.admin_headers,
        )
        showtime_id = res.json()["id"]

        # Update price and movie without changing time -> should succeed (not conflict with itself)
        res_update = client.put(
            f"/api/admin/showtimes/{showtime_id}",
            json={"price": 110000},
            headers=self.admin_headers,
        )
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(float(res_update.json()["price"]), 110000.0)

    def test_delete_showtime(self):
        start = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        res = client.post(
            "/api/admin/showtimes",
            json={"movie_id": 1, "room_id": 1, "start_time": start.isoformat(), "price": 95000},
            headers=self.admin_headers,
        )
        showtime_id = res.json()["id"]

        del_res = client.delete(f"/api/admin/showtimes/{showtime_id}", headers=self.admin_headers)
        self.assertEqual(del_res.status_code, 200)

        # Verify it's gone
        get_res = client.get(f"/api/admin/showtimes/{showtime_id}", headers=self.admin_headers)
        self.assertEqual(get_res.status_code, 404)

    def test_delete_showtime_with_paid_booking_blocked(self):
        db = TestingSessionLocal()
        start = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=120)
        st = Showtime(movie_id=1, room_id=1, start_time=start, end_time=end, price=Decimal("95000"))
        db.add(st)
        db.commit()
        db.refresh(st)

        # Add paid booking
        booking = Booking(
            booking_code="BK-TEST-123",
            user_id=self.normal_user_id,
            showtime_id=st.id,
            total_price=Decimal("95000"),
            status="DA_THANH_TOAN",
        )
        db.add(booking)
        db.commit()
        st_id = st.id
        db.close()

        # Delete without force -> blocked
        del_res = client.delete(f"/api/admin/showtimes/{st_id}", headers=self.admin_headers)
        self.assertEqual(del_res.status_code, 400)
        self.assertIn("vé được thanh toán", del_res.json()["detail"])

        # Delete with force=True -> succeeds
        del_force = client.delete(f"/api/admin/showtimes/{st_id}?force=true", headers=self.admin_headers)
        self.assertEqual(del_force.status_code, 200)

    def test_guard_unauthorized(self):
        # Without token -> 401
        res = client.get("/api/admin/showtimes")
        self.assertEqual(res.status_code, 401)

        # Normal user -> 403
        res = client.get("/api/admin/showtimes", headers=self.user_headers)
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
