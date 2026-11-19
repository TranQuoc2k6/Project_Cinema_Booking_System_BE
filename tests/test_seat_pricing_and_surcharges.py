import os
import sys
import unittest
from datetime import date, datetime, timedelta, time
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
from app.models.seat import Seat
from app.models.movie import Movie
from app.models.showtime import Showtime
from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.core.pricing import (
    calculate_seat_price,
    get_showtime_surcharges,
    is_weekend_showtime,
    is_peak_hour_showtime,
    get_pricing_breakdown,
    get_pricing_config,
    update_pricing_config,
    DEFAULT_PRICING_CONFIG,
)
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


client = TestClient(app)


class TestSeatPricingAndSurcharges(unittest.TestCase):
    def setUp(self):
        # Reset pricing config to default before each test
        update_pricing_config(DEFAULT_PRICING_CONFIG)

        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        db = TestingSessionLocal()

        # Seed roles & users
        admin_role = Role(id=1, name="admin")
        customer_role = Role(id=2, name="customer")
        db.add_all([admin_role, customer_role])
        db.commit()

        self.admin_user = User(
            id=1,
            email="admin_pricing@test.com",
            full_name="Admin Pricing",
            password_hash=hash_password("admin123"),
            role_id=1,
            is_active=True,
        )
        self.normal_user = User(
            id=2,
            email="user_pricing@test.com",
            full_name="Normal User",
            password_hash=hash_password("user123"),
            role_id=2,
            is_active=True,
        )
        db.add_all([self.admin_user, self.normal_user])
        db.commit()

        # Seed Cinema & Room
        self.cinema = Cinema(id=1, name="Lumen Vincom", address="191 Ba Trieu", city="Ha Noi")
        db.add(self.cinema)
        db.commit()

        self.room = Room(id=1, cinema_id=1, name="Screen 01", room_type="2D", total_seats=3)
        db.add(self.room)
        db.commit()

        # Seed Seats of different types
        self.seat_std = Seat(id=1, room_id=1, seat_number="A01", seat_row="A", seat_column=1, seat_type="standard", is_active=True)
        self.seat_vip = Seat(id=2, room_id=1, seat_number="B01", seat_row="B", seat_column=1, seat_type="vip", is_active=True)
        self.seat_cpl = Seat(id=3, room_id=1, seat_number="C01", seat_row="C", seat_column=1, seat_type="couple", is_active=True)
        db.add_all([self.seat_std, self.seat_vip, self.seat_cpl])
        db.commit()

        # Seed Movie
        self.movie = Movie(id=1, title="Dune 2", slug="dune-2", duration_minutes=120, release_date=date(2026, 11, 10), status="now_showing")
        db.add(self.movie)
        db.commit()

        self.admin_id = self.admin_user.id
        self.user_id = self.normal_user.id

        db.close()

        self.admin_token = create_access_token(data={"sub": str(self.admin_id), "role": "admin"})
        self.user_token = create_access_token(data={"sub": str(self.user_id), "role": "customer"})
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.user_headers = {"Authorization": f"Bearer {self.user_token}"}

    def tearDown(self):
        update_pricing_config(DEFAULT_PRICING_CONFIG)
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.clear()

    # -----------------------------------------------------------------------
    # Unit Tests for Core Pricing Engine
    # -----------------------------------------------------------------------

    def test_regular_weekday_morning_pricing(self):
        """Thứ 2, 09:30 (Không phải cuối tuần, không phải giờ vàng).
        Base: 80,000 -> Standard: 80,000; VIP (x1.5): 120,000; Couple (x2.0): 160,000."""
        # 2026-11-23 is Monday
        monday_morning = datetime(2026, 11, 23, 9, 30)
        self.assertFalse(is_weekend_showtime(monday_morning))
        self.assertFalse(is_peak_hour_showtime(monday_morning))

        surcharges = get_showtime_surcharges(monday_morning)
        self.assertEqual(surcharges["total_surcharge"], Decimal("0.00"))

        p_std = calculate_seat_price(Decimal("80000"), "standard", monday_morning)
        p_vip = calculate_seat_price(Decimal("80000"), "vip", monday_morning)
        p_cpl = calculate_seat_price(Decimal("80000"), "couple", monday_morning)

        self.assertEqual(p_std, Decimal("80000.00"))
        self.assertEqual(p_vip, Decimal("120000.00"))
        self.assertEqual(p_cpl, Decimal("160000.00"))

    def test_weekday_peak_hour_pricing(self):
        """Thứ 3, 19:30 (Giờ vàng: +10,000 phụ thu).
        Slot base: 80,000 + 10,000 = 90,000.
        Standard: 90,000; VIP (x1.5): 135,000; Couple (x2.0): 180,000."""
        # 2026-11-24 is Tuesday
        tuesday_peak = datetime(2026, 11, 24, 19, 30)
        self.assertFalse(is_weekend_showtime(tuesday_peak))
        self.assertTrue(is_peak_hour_showtime(tuesday_peak))

        surcharges = get_showtime_surcharges(tuesday_peak)
        self.assertEqual(surcharges["peak_hour_surcharge"], Decimal("10000.00"))
        self.assertEqual(surcharges["total_surcharge"], Decimal("10000.00"))

        p_std = calculate_seat_price(Decimal("80000"), "standard", tuesday_peak)
        p_vip = calculate_seat_price(Decimal("80000"), "vip", tuesday_peak)
        p_cpl = calculate_seat_price(Decimal("80000"), "couple", tuesday_peak)

        self.assertEqual(p_std, Decimal("90000.00"))
        self.assertEqual(p_vip, Decimal("135000.00"))
        self.assertEqual(p_cpl, Decimal("180000.00"))

    def test_weekend_offpeak_pricing(self):
        """Thứ 7, 14:00 (Cuối tuần, giờ thường: +10,000 phụ thu cuối tuần).
        Slot base: 80,000 + 10,000 = 90,000.
        Standard: 90,000; VIP (x1.5): 135,000; Couple (x2.0): 180,000."""
        # 2026-11-28 is Saturday
        saturday_afternoon = datetime(2026, 11, 28, 14, 0)
        self.assertTrue(is_weekend_showtime(saturday_afternoon))
        self.assertFalse(is_peak_hour_showtime(saturday_afternoon))

        surcharges = get_showtime_surcharges(saturday_afternoon)
        self.assertEqual(surcharges["weekend_surcharge"], Decimal("10000.00"))
        self.assertEqual(surcharges["peak_hour_surcharge"], Decimal("0.00"))
        self.assertEqual(surcharges["total_surcharge"], Decimal("10000.00"))

        p_std = calculate_seat_price(Decimal("80000"), "standard", saturday_afternoon)
        p_vip = calculate_seat_price(Decimal("80000"), "vip", saturday_afternoon)
        p_cpl = calculate_seat_price(Decimal("80000"), "couple", saturday_afternoon)

        self.assertEqual(p_std, Decimal("90000.00"))
        self.assertEqual(p_vip, Decimal("135000.00"))
        self.assertEqual(p_cpl, Decimal("180000.00"))

    def test_weekend_peak_hour_pricing(self):
        """Chủ nhật, 20:00 (Cả cuối tuần + giờ vàng: +10,000 + 10,000 = +20,000).
        Slot base: 80,000 + 20,000 = 100,000.
        Standard: 100,000; VIP (x1.5): 150,000; Couple (x2.0): 200,000."""
        # 2026-11-29 is Sunday
        sunday_peak = datetime(2026, 11, 29, 20, 0)
        self.assertTrue(is_weekend_showtime(sunday_peak))
        self.assertTrue(is_peak_hour_showtime(sunday_peak))

        surcharges = get_showtime_surcharges(sunday_peak)
        self.assertEqual(surcharges["weekend_surcharge"], Decimal("10000.00"))
        self.assertEqual(surcharges["peak_hour_surcharge"], Decimal("10000.00"))
        self.assertEqual(surcharges["total_surcharge"], Decimal("20000.00"))

        p_std = calculate_seat_price(Decimal("80000"), "standard", sunday_peak)
        p_vip = calculate_seat_price(Decimal("80000"), "vip", sunday_peak)
        p_cpl = calculate_seat_price(Decimal("80000"), "couple", sunday_peak)

        self.assertEqual(p_std, Decimal("100000.00"))
        self.assertEqual(p_vip, Decimal("150000.00"))
        self.assertEqual(p_cpl, Decimal("200000.00"))

    def test_friday_evening_counts_as_weekend(self):
        """Tối Thứ 6 lúc 18:30 (Thứ 6 >= 17:00 tính là cuối tuần + giờ vàng 18:30)."""
        # 2026-11-27 is Friday
        friday_evening = datetime(2026, 11, 27, 18, 30)
        self.assertTrue(is_weekend_showtime(friday_evening))
        self.assertTrue(is_peak_hour_showtime(friday_evening))

    # -----------------------------------------------------------------------
    # Integration Tests for API: GET /api/showtimes/{id}/seats
    # -----------------------------------------------------------------------

    def test_get_showtime_seat_map_with_pricing(self):
        """API trả giá từng ghế cho trang chọn ghế kèm thông tin phụ thu."""
        db = TestingSessionLocal()
        # Tạo suất chiếu rơi vào Giờ Vàng Chủ Nhật: 20:00 (Base 80,000)
        show_time = datetime(2026, 11, 29, 20, 0)
        end_time = show_time + timedelta(minutes=120)
        st = Showtime(id=10, movie_id=1, room_id=1, start_time=show_time, end_time=end_time, price=Decimal("80000.00"))
        db.add(st)
        db.commit()
        db.close()

        res = client.get("/api/showtimes/10/seats")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Metadata phụ thu
        self.assertTrue(data["is_weekend"])
        self.assertTrue(data["is_peak_hour"])
        self.assertEqual(float(data["weekend_surcharge"]), 10000.0)
        self.assertEqual(float(data["peak_hour_surcharge"]), 10000.0)

        # Giá từng ghế trong sơ đồ
        rows = data["rows"]
        # Ghế Standard A01: 100,000
        seat_a = rows["A"][0]
        self.assertEqual(seat_a["seat_type"], "standard")
        self.assertEqual(float(seat_a["price"]), 100000.0)

        # Ghế VIP B01: 150,000
        seat_b = rows["B"][0]
        self.assertEqual(seat_b["seat_type"], "vip")
        self.assertEqual(float(seat_b["price"]), 150000.0)

        # Ghế Couple C01: 200,000
        seat_c = rows["C"][0]
        self.assertEqual(seat_c["seat_type"], "couple")
        self.assertEqual(float(seat_c["price"]), 200000.0)

    def test_get_showtime_pricing_breakdown_endpoint(self):
        """API GET /api/showtimes/{id}/pricing trả chi tiết phân tích giá."""
        db = TestingSessionLocal()
        show_time = datetime(2026, 11, 24, 19, 30)  # Thứ 3 giờ vàng (Base 80k + 10k giờ vàng)
        st = Showtime(id=11, movie_id=1, room_id=1, start_time=show_time, end_time=show_time + timedelta(minutes=120), price=Decimal("80000.00"))
        db.add(st)
        db.commit()
        db.close()

        res = client.get("/api/showtimes/11/pricing")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        pricing = data["pricing"]
        self.assertEqual(pricing["base_price"], 80000.0)
        self.assertFalse(pricing["is_weekend"])
        self.assertTrue(pricing["is_peak_hour"])
        self.assertEqual(pricing["seat_prices"]["standard"], 90000.0)
        self.assertEqual(pricing["seat_prices"]["vip"], 135000.0)
        self.assertEqual(pricing["seat_prices"]["couple"], 180000.0)

    # -----------------------------------------------------------------------
    # Test Hold Seats with Surcharged Pricing
    # -----------------------------------------------------------------------

    def test_hold_seats_calculates_surcharged_total(self):
        """Khi khách hàng giữ ghế, tổng tiền phải đúng theo giá đã có phụ thu."""
        db = TestingSessionLocal()
        # Suất chiếu Chủ Nhật 20:00 (Standard 100k, VIP 150k)
        show_time = datetime(2026, 11, 29, 20, 0)
        st = Showtime(id=12, movie_id=1, room_id=1, start_time=show_time, end_time=show_time + timedelta(minutes=120), price=Decimal("80000.00"))
        db.add(st)
        db.commit()
        db.close()

        # Chọn 1 ghế Standard (id=1, 100k) và 1 ghế VIP (id=2, 150k) -> Tổng 250k
        payload = {
            "showtime_id": 12,
            "seat_ids": [1, 2]
        }
        res = client.post("/api/bookings/hold", json=payload, headers=self.user_headers)
        self.assertEqual(res.status_code, 201)
        booking_data = res.json()
        self.assertEqual(float(booking_data["total_price"]), 250000.0)

    # -----------------------------------------------------------------------
    # Admin Pricing Config Endpoints
    # -----------------------------------------------------------------------

    def test_admin_get_and_update_pricing_config(self):
        """Admin có thể xem và cập nhật cấu hình giá vé, phụ thu cuối tuần & giờ vàng."""
        # 1. Get config
        res_get = client.get("/api/admin/showtimes/pricing-config", headers=self.admin_headers)
        self.assertEqual(res_get.status_code, 200)
        data = res_get.json()
        self.assertEqual(data["weekend_surcharge"], 10000.0)
        self.assertEqual(data["seat_multipliers"]["vip"], 1.5)

        # 2. Update config: tăng phụ thu cuối tuần lên 15,000 VND và VIP lên 1.6x
        update_payload = {
            "weekend_surcharge": 15000.0,
            "seat_multipliers": {
                "standard": 1.0,
                "vip": 1.6,
                "couple": 2.2
            }
        }
        res_put = client.put("/api/admin/showtimes/pricing-config", json=update_payload, headers=self.admin_headers)
        self.assertEqual(res_put.status_code, 200)
        updated = res_put.json()
        self.assertEqual(updated["weekend_surcharge"], 15000.0)
        self.assertEqual(updated["seat_multipliers"]["vip"], 1.6)

        # 3. Verify price calculation immediately reflects new config
        # Saturday morning (Base 80k + 15k weekend = 95k)
        sat_morning = datetime(2026, 11, 28, 10, 0)
        p_std = calculate_seat_price(Decimal("80000"), "standard", sat_morning)
        p_vip = calculate_seat_price(Decimal("80000"), "vip", sat_morning)
        self.assertEqual(p_std, Decimal("95000.00"))
        # VIP: 95,000 * 1.6 = 152,000
        self.assertEqual(p_vip, Decimal("152000.00"))

    def test_pricing_config_unauthorized(self):
        """Người dùng thường không được phép sửa cấu hình giá vé (403)."""
        res = client.put("/api/admin/showtimes/pricing-config", json={"weekend_surcharge": 20000.0}, headers=self.user_headers)
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
