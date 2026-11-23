"""
Unit tests cho Task T3C6CE6:
  - Xác nhận đặt vé từ ghế đang giữ
  - Tính lại tiền ở server
  - Tự chuyển giữ chỗ quá hạn sang HET_HAN để trả ghế
"""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

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
from app.schemas.booking import (
    BookingConfirmRequest,
    BookingConfirmResponse,
    CleanExpiredResponse,
)
from app.services.booking_service import clean_expired_holds, confirm_booking, hold_seats


# ---------------------------------------------------------------------------
# Fixture SQLite in-memory để kiểm thử độc lập, không phụ thuộc MySQL ngoài
# ---------------------------------------------------------------------------
@pytest.fixture
def in_memory_db():
    from database import Base
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed Role & User
    user_role = Role(id=1, name="USER", description="Khách hàng")
    admin_role = Role(id=2, name="ADMIN", description="Quản trị viên")
    session.add_all([user_role, admin_role])
    session.flush()

    user1 = User(
        id=1,
        full_name="Nguyễn Văn A",
        email="user1@example.com",
        password_hash="hashed_pw_1",
        role_id=1,
        is_active=True,
    )
    user2 = User(
        id=2,
        full_name="Trần Thị B",
        email="user2@example.com",
        password_hash="hashed_pw_2",
        role_id=1,
        is_active=True,
    )
    admin_user = User(
        id=3,
        full_name="Admin Master",
        email="admin@example.com",
        password_hash="hashed_admin_pw",
        role_id=2,
        is_active=True,
    )
    session.add_all([user1, user2, admin_user])

    # Seed Cinema, Room, Movie, Showtime, Seats
    cinema = Cinema(id=1, name="CGV Test Cinema", address="123 Test St", city="Hà Nội")
    session.add(cinema)
    session.flush()

    room = Room(id=1, cinema_id=1, name="Phòng 01 Laser", total_seats=10, room_type="2D")
    session.add(room)
    session.flush()

    movie = Movie(
        id=1,
        title="Dune: Part Two",
        slug="dune-part-two",
        duration_minutes=166,
        release_date=datetime.utcnow().date(),
        status="NOW_SHOWING",
    )
    session.add(movie)
    session.flush()

    # Suất chiếu giá cơ bản 100.000 đ
    showtime = Showtime(
        id=1,
        movie_id=1,
        room_id=1,
        start_time=datetime.utcnow() + timedelta(hours=2),
        end_time=datetime.utcnow() + timedelta(hours=5),
        price=Decimal("100000.00"),
    )
    session.add(showtime)
    session.flush()

    # Ghế 1: standard (x1.0 = 100k)
    # Ghế 2: vip (x1.5 = 150k)
    # Ghế 3: couple (x2.0 = 200k)
    seat1 = Seat(id=1, room_id=1, seat_number="A1", seat_row="A", seat_column=1, seat_type="standard", is_active=True)
    seat2 = Seat(id=2, room_id=1, seat_number="A2", seat_row="A", seat_column=2, seat_type="vip", is_active=True)
    seat3 = Seat(id=3, room_id=1, seat_number="A3", seat_row="A", seat_column=3, seat_type="couple", is_active=True)
    seat4 = Seat(id=4, room_id=1, seat_number="A4", seat_row="A", seat_column=4, seat_type="standard", is_active=True)
    session.add_all([seat1, seat2, seat3, seat4])
    session.commit()

    yield session
    session.close()


# ---------------------------------------------------------------------------
# TEST SUITE 1: Schemas validation
# ---------------------------------------------------------------------------
class TestBookingConfirmationSchemas:

    def test_booking_confirm_request_valid(self):
        req = BookingConfirmRequest(booking_id=10, payment_method="VNPAY")
        assert req.booking_id == 10
        assert req.payment_method == "VNPAY"

    def test_booking_confirm_request_with_code(self):
        req = BookingConfirmRequest(booking_code="BK-20261118-001", payment_method="MOMO")
        assert req.booking_code == "BK-20261118-001"
        assert req.payment_method == "MOMO"

    def test_clean_expired_response_schema(self):
        resp = CleanExpiredResponse(
            success=True,
            expired_bookings_count=2,
            released_seats_count=4,
            message="Đã dọn dẹp thành công",
        )
        assert resp.expired_bookings_count == 2
        assert resp.released_seats_count == 4


# ---------------------------------------------------------------------------
# TEST SUITE 2: Xác nhận đặt vé từ ghế đang giữ & tính lại tiền ở server
# ---------------------------------------------------------------------------
class TestConfirmBookingService:

    def test_confirm_booking_success_and_recalculate_price(self, in_memory_db):
        user = in_memory_db.query(User).filter(User.id == 1).first()

        # 1. Giữ 2 ghế: A1 (standard) và A2 (vip)
        # Giá cơ bản: 100k -> A1 = 100k, A2 = 150k -> Tổng = 250k
        booking = hold_seats(
            showtime_id=1,
            seat_ids=[1, 2],
            user_id=user.id,
            db=in_memory_db,
        )
        assert booking.status == "GIU_CHO"
        assert booking.held_until is not None

        # 2. Xác nhận đặt vé
        result = confirm_booking(
            db=in_memory_db,
            user=user,
            booking_id=booking.id,
            payment_method="MOMO",
            transaction_id="MOMO-TEST-12345",
        )

        assert result["success"] is True
        assert result["recalculated_price"] == Decimal("250000.00")
        assert result["payment_status"] == "SUCCESS"

        # Kiểm tra bản ghi trong DB
        in_memory_db.refresh(booking)
        assert booking.status == "DA_THANH_TOAN"
        assert booking.held_until is None  # Đã thanh toán thì không còn hạn giữ chỗ
        assert booking.total_price == Decimal("250000.00")

        # Kiểm tra Payment được tạo
        payment = in_memory_db.query(Payment).filter(Payment.booking_id == booking.id).first()
        assert payment is not None
        assert payment.status == "SUCCESS"
        assert payment.payment_method == "MOMO"
        assert payment.amount == Decimal("250000.00")

    def test_confirm_booking_cannot_confirm_others_booking(self, in_memory_db):
        user1 = in_memory_db.query(User).filter(User.id == 1).first()
        user2 = in_memory_db.query(User).filter(User.id == 2).first()

        # User 1 giữ ghế
        booking = hold_seats(showtime_id=1, seat_ids=[1], user_id=user1.id, db=in_memory_db)

        # User 2 cố gắng xác nhận vé của User 1 -> 403 Forbidden
        with pytest.raises(HTTPException) as exc_info:
            confirm_booking(db=in_memory_db, user=user2, booking_id=booking.id)
        assert exc_info.value.status_code == 403

    def test_confirm_booking_cannot_confirm_twice(self, in_memory_db):
        user = in_memory_db.query(User).filter(User.id == 1).first()

        # Giữ ghế và xác nhận lần 1
        booking = hold_seats(showtime_id=1, seat_ids=[1], user_id=user.id, db=in_memory_db)
        confirm_booking(db=in_memory_db, user=user, booking_id=booking.id)

        # Xác nhận lần 2 -> 400 Bad Request
        with pytest.raises(HTTPException) as exc_info:
            confirm_booking(db=in_memory_db, user=user, booking_id=booking.id)
        assert exc_info.value.status_code == 400
        assert "đã được thanh toán" in exc_info.value.detail


# ---------------------------------------------------------------------------
# TEST SUITE 3: Tự động chuyển giữ chỗ quá hạn sang HET_HAN để trả ghế
# ---------------------------------------------------------------------------
class TestAutoExpireOverdueHolds:

    def test_clean_expired_holds_releases_seats(self, in_memory_db):
        user1 = in_memory_db.query(User).filter(User.id == 1).first()
        user2 = in_memory_db.query(User).filter(User.id == 2).first()

        # User 1 giữ ghế A1
        booking = hold_seats(showtime_id=1, seat_ids=[1], user_id=user1.id, db=in_memory_db)

        # Giả lập thời gian giữ chỗ đã trôi qua (quá hạn 10 phút)
        booking.held_until = datetime.utcnow() - timedelta(minutes=1)
        in_memory_db.commit()

        # Chạy hàm dọn dẹp giữ chỗ quá hạn
        cleanup_stats = clean_expired_holds(in_memory_db)
        assert cleanup_stats["expired_bookings_count"] == 1
        assert cleanup_stats["released_seats_count"] == 1

        # Đơn vé của User 1 phải đổi sang HET_HAN và mất hạn giữ chỗ
        in_memory_db.refresh(booking)
        assert booking.status == "HET_HAN"
        assert booking.held_until is None

        # Ghế A1 đã được giải phóng -> User 2 có thể giữ lại ghế A1 mà không bị 409 Conflict!
        new_booking = hold_seats(showtime_id=1, seat_ids=[1], user_id=user2.id, db=in_memory_db)
        assert new_booking.status == "GIU_CHO"
        assert new_booking.user_id == user2.id

    def test_confirm_expired_booking_fails_and_auto_releases(self, in_memory_db):
        user = in_memory_db.query(User).filter(User.id == 1).first()

        # Giữ ghế
        booking = hold_seats(showtime_id=1, seat_ids=[1], user_id=user.id, db=in_memory_db)

        # Giả lập hết hạn giữ chỗ
        booking.held_until = datetime.utcnow() - timedelta(seconds=10)
        in_memory_db.commit()

        # Cố gắng xác nhận vé quá hạn -> Phải báo lỗi và tự chuyển sang HET_HAN
        with pytest.raises(HTTPException) as exc_info:
            confirm_booking(db=in_memory_db, user=user, booking_id=booking.id)

        assert exc_info.value.status_code == 400
        assert "quá hạn" in exc_info.value.detail or "HET_HAN" in exc_info.value.detail

        in_memory_db.refresh(booking)
        assert booking.status == "HET_HAN"
