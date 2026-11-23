"""
Unit tests cho Task T3C72CC:
  [Bonus] Mã QR trên vé điện tử:
  - Sinh QR chứa mã vé
  - Trang tra cứu / xác nhận vé khi quét QR
  - Chống quét trùng (Duplicate Check-in / Anti-fraud)
  - Kiểm tra các trạng thái: ĐÃ THANH TOÁN (hợp lệ), ĐÃ HỦY, HẾT HẠN, CHỜ THANH TOÁN
"""
from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.cinema import Cinema
from app.models.movie import Movie
from app.models.payment import Payment
from app.models.role import Role
from app.models.room import Room
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.models.user import User
from app.services.booking_service import (
    verify_ticket_by_code,
    checkin_ticket_by_code,
)


@pytest.fixture
def in_memory_db():
    from database import Base
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Seed Roles & Users
    user_role = Role(id=1, name="USER", description="Khách hàng")
    admin_role = Role(id=2, name="ADMIN", description="Quản trị viên")
    session.add_all([user_role, admin_role])
    session.flush()

    customer = User(
        id=1,
        full_name="Nguyễn Đình Đức",
        email="duc.nguyen@cinema.com",
        phone="0987654321",
        password_hash="fakehash",
        role_id=1,
    )
    session.add(customer)
    session.flush()

    # 2. Cinema, Room & Seats
    cinema = Cinema(id=1, name="LUMEN Royal City", address="72A Nguyễn Trãi", city="Hà Nội")
    session.add(cinema)
    session.flush()

    room = Room(id=1, cinema_id=1, name="Phòng Chiếu 01 (VIP Laser)", total_seats=20, room_type="2D Digital")
    session.add(room)
    session.flush()

    seat_a1 = Seat(id=1, room_id=1, seat_row="A", seat_column=1, seat_number="A01", seat_type="standard", is_active=True)
    seat_a2 = Seat(id=2, room_id=1, seat_row="A", seat_column=2, seat_number="A02", seat_type="vip", is_active=True)
    session.add_all([seat_a1, seat_a2])
    session.flush()

    # 3. Movie & Showtime
    movie = Movie(
        id=1,
        title="Dune: Hành Tinh Cát 2",
        slug="dune-part-two",
        description="Bom tấn viễn tưởng đỉnh cao",
        duration_minutes=166,
        release_date=datetime.utcnow().date(),
        poster_url="https://image.tmdb.org/t/p/original/dune2.jpg",
        status="NOW_SHOWING",
    )
    session.add(movie)
    session.flush()

    # Suất chiếu tương lai cách 3 tiếng
    showtime = Showtime(
        id=1,
        movie_id=1,
        room_id=1,
        start_time=datetime.utcnow() + timedelta(hours=3),
        end_time=datetime.utcnow() + timedelta(hours=5, minutes=46),
        price=Decimal("110000.00"),
    )
    session.add(showtime)
    session.flush()

    # 4. Tạo các vé mẫu kiểm thử
    # Vé 1: Đã thanh toán hợp lệ
    b_paid = Booking(
        id=101,
        booking_code="BK-QR-PAID-01",
        user_id=1,
        showtime_id=1,
        total_price=Decimal("250000.00"),
        status="DA_THANH_TOAN",
        held_until=None,
        is_checked_in=False,
        checked_in_at=None,
    )
    session.add(b_paid)
    session.flush()

    bs1 = BookingSeat(id=1, booking_id=101, showtime_id=1, seat_id=1, price=Decimal("110000.00"))
    bs2 = BookingSeat(id=2, booking_id=101, showtime_id=1, seat_id=2, price=Decimal("140000.00"))
    session.add_all([bs1, bs2])

    p1 = Payment(
        id=1,
        booking_id=101,
        amount=Decimal("250000.00"),
        payment_method="MOMO",
        status="SUCCESS",
        transaction_id="TXN-QR-001",
    )
    session.add(p1)

    # Vé 2: Đã bị hủy
    b_cancelled = Booking(
        id=102,
        booking_code="BK-QR-CANCELLED-02",
        user_id=1,
        showtime_id=1,
        total_price=Decimal("110000.00"),
        status="DA_HUY",
        held_until=None,
        is_checked_in=False,
    )
    session.add(b_cancelled)

    # Vé 3: Đang giữ chỗ / Chưa thanh toán
    b_pending = Booking(
        id=103,
        booking_code="BK-QR-PENDING-03",
        user_id=1,
        showtime_id=1,
        total_price=Decimal("110000.00"),
        status="GIU_CHO",
        held_until=datetime.utcnow() + timedelta(minutes=10),
        is_checked_in=False,
    )
    session.add(b_pending)

    session.commit()

    yield session
    session.close()


class TestQRTicketVerificationAndCheckIn:

    def test_verify_ticket_success_with_valid_code(self, in_memory_db):
        """Tra cứu thành công vé hợp lệ khi quét mã QR"""
        res = verify_ticket_by_code(in_memory_db, "BK-QR-PAID-01")

        assert res["success"] is True
        assert res["booking_code"] == "BK-QR-PAID-01"
        assert res["status"] == "DA_THANH_TOAN"
        assert res["payment_status"] == "PAID"
        assert res["is_checked_in"] is False
        assert res["is_valid_for_entry"] is True
        assert res["customer_name"] == "Nguyễn Đình Đức"
        assert res["customer_phone_masked"] == "098****321"
        assert res["movie"]["title"] == "Dune: Hành Tinh Cát 2"
        assert res["cinema"]["name"] == "LUMEN Royal City"
        assert len(res["seats"]) == 2
        assert res["seats"][0]["seat_number"] == "A01"
        assert res["seats"][1]["seat_number"] == "A02"
        assert "ticket-check.html?code=BK-QR-PAID-01" in res["qr_verify_url"]

    def test_verify_ticket_not_found_raises_404(self, in_memory_db):
        """Quét mã QR giả hoặc không tồn tại -> 404 Not Found"""
        with pytest.raises(HTTPException) as exc_info:
            verify_ticket_by_code(in_memory_db, "BK-NON-EXISTENT")
        assert exc_info.value.status_code == 404
        assert "Không tìm thấy vé" in str(exc_info.value.detail)

    def test_verify_ticket_shows_cancelled_status(self, in_memory_db):
        """Quét vé đã hủy -> Hiển thị cảnh báo vé đã hủy và không thể vào rạp"""
        res = verify_ticket_by_code(in_memory_db, "BK-QR-CANCELLED-02")
        assert res["status"] == "DA_HUY"
        assert res["payment_status"] == "CANCELLED"
        assert res["is_valid_for_entry"] is False

    def test_verify_ticket_shows_pending_status(self, in_memory_db):
        """Quét vé chưa thanh toán -> is_valid_for_entry = False"""
        res = verify_ticket_by_code(in_memory_db, "BK-QR-PENDING-03")
        assert res["status"] == "GIU_CHO"
        assert res["payment_status"] == "PENDING"
        assert res["is_valid_for_entry"] is False

    def test_checkin_ticket_success_first_time(self, in_memory_db):
        """Nhân viên quét QR bấm Xác nhận vào rạp lần đầu thành công"""
        res = checkin_ticket_by_code(in_memory_db, "BK-QR-PAID-01")

        assert res["success"] is True
        assert "Xác nhận vé thành công" in res["message"]
        assert res["booking_code"] == "BK-QR-PAID-01"
        assert res["movie_title"] == "Dune: Hành Tinh Cát 2"
        assert res["total_seats"] == 2
        assert "A01" in res["seats"]
        assert "A02" in res["seats"]

        # Kiểm tra CSDL đã được cập nhật
        refreshed = in_memory_db.query(Booking).filter(Booking.booking_code == "BK-QR-PAID-01").first()
        assert refreshed.is_checked_in is True
        assert refreshed.checked_in_at is not None

    def test_checkin_ticket_duplicate_raises_400_anti_fraud(self, in_memory_db):
        """Chống quét vé lần 2: Đã soát vé rồi thì từ chối và cảnh báo kèm thời gian"""
        # Soát vé lần 1
        checkin_ticket_by_code(in_memory_db, "BK-QR-PAID-01")

        # Thử soát vé lần 2 với cùng mã vé
        with pytest.raises(HTTPException) as exc_info:
            checkin_ticket_by_code(in_memory_db, "BK-QR-PAID-01")

        assert exc_info.value.status_code == 400
        assert "CẢNH BÁO" in exc_info.value.detail
        assert "ĐÃ ĐƯỢC SOÁT VÀO RẠP" in exc_info.value.detail
        assert "Không thể tái sử dụng vé" in exc_info.value.detail

    def test_checkin_ticket_cancelled_raises_400(self, in_memory_db):
        """Cố tình soát vé đã bị hủy -> Bị từ chối"""
        with pytest.raises(HTTPException) as exc_info:
            checkin_ticket_by_code(in_memory_db, "BK-QR-CANCELLED-02")
        assert exc_info.value.status_code == 400
        assert "đã bị hủy" in exc_info.value.detail

    def test_checkin_ticket_unpaid_raises_400(self, in_memory_db):
        """Cố tình soát vé chưa thanh toán -> Bị từ chối"""
        with pytest.raises(HTTPException) as exc_info:
            checkin_ticket_by_code(in_memory_db, "BK-QR-PENDING-03")
        assert exc_info.value.status_code == 400
        assert "chưa hoàn tất thanh toán" in exc_info.value.detail

    def test_checkin_ticket_not_found_raises_404(self, in_memory_db):
        """Soát vé với mã không tồn tại -> 404"""
        with pytest.raises(HTTPException) as exc_info:
            checkin_ticket_by_code(in_memory_db, "BK-FAKE-CODE-999")
        assert exc_info.value.status_code == 404
