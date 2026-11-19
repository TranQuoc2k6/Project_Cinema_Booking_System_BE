"""
Unit tests cho Task T3C6D00:
  - API Thanh toán mô phỏng (Sandbox)
  - Chọn phương thức thanh toán
  - Kết quả thành công (SUCCESS) cập nhật trạng thái vé sang DA_THANH_TOAN
  - Kết quả thất bại (FAILED) ghi nhận lỗi và giữ trạng thái vé
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
from app.routers.payments import get_payment_methods, process_sandbox_payment
from app.schemas.payment import PaymentSandboxRequest, PaymentStatusEnum
from app.services.booking_service import hold_seats
from database import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed User & Role
    user_role = Role(id=1, name="USER", description="Khách hàng")
    admin_role = Role(id=2, name="ADMIN", description="Quản trị viên")
    session.add_all([user_role, admin_role])
    session.flush()

    user = User(id=1, full_name="Trần Văn Khách", email="khach@cinema.com", password_hash="hash", role_id=1, is_active=True)
    other_user = User(id=2, full_name="Người Khác", email="other@cinema.com", password_hash="hash", role_id=1, is_active=True)
    session.add_all([user, other_user])

    # Seed Cinema, Room, Movie, Showtime, Seats
    cinema = Cinema(id=1, name="CGV Test", address="Hà Nội", city="Hà Nội")
    session.add(cinema)
    session.flush()

    room = Room(id=1, cinema_id=1, name="Phòng 01", total_seats=10, room_type="2D")
    session.add(room)
    session.flush()

    movie = Movie(id=1, title="Phim Test", slug="phim-test", duration_minutes=120, release_date=datetime.utcnow().date(), status="NOW_SHOWING")
    session.add(movie)
    session.flush()

    showtime = Showtime(id=1, movie_id=1, room_id=1, start_time=datetime.utcnow() + timedelta(hours=2), end_time=datetime.utcnow() + timedelta(hours=4), price=Decimal("90000.00"))
    session.add(showtime)
    session.flush()

    seat = Seat(id=1, room_id=1, seat_number="A1", seat_row="A", seat_column=1, seat_type="standard", is_active=True)
    session.add(seat)
    session.commit()

    yield session
    session.close()


class TestPaymentSandbox:

    def test_get_payment_methods(self):
        """Kiểm tra danh sách cổng thanh toán hỗ trợ (MoMo, VNPAY, Visa, ZaloPay)."""
        methods = get_payment_methods()
        assert len(methods) >= 3
        codes = [m.code for m in methods]
        assert "MOMO" in codes
        assert "VNPAY" in codes
        assert "VISA" in codes

    def test_sandbox_payment_success_updates_ticket_status(self, db_session):
        """Mô phỏng thanh toán thành công -> cập nhật trạng thái vé sang DA_THANH_TOAN."""
        user = db_session.query(User).filter(User.id == 1).first()

        # 1. Giữ ghế
        booking = hold_seats(showtime_id=1, seat_ids=[1], user_id=user.id, db=db_session)
        assert booking.status == "GIU_CHO"

        # 2. Thanh toán mô phỏng thành công qua MoMo
        req = PaymentSandboxRequest(
            booking_id=booking.id,
            payment_method="MOMO",
            status=PaymentStatusEnum.SUCCESS,
            amount=Decimal("90000.00"),
        )
        res = process_sandbox_payment(payload=req, current_user=user, db=db_session)

        assert res.status == "SUCCESS"
        assert res.booking_status == "DA_THANH_TOAN"
        assert res.payment_method == "MOMO"

        # Kiểm tra vé trong DB
        db_session.refresh(booking)
        assert booking.status == "DA_THANH_TOAN"
        assert booking.held_until is None

        # Kiểm tra bản ghi Payment
        payment = db_session.query(Payment).filter(Payment.booking_id == booking.id).first()
        assert payment is not None
        assert payment.status == "SUCCESS"

    def test_sandbox_payment_failure_keeps_ticket_held(self, db_session):
        """Mô phỏng thanh toán thất bại -> ghi nhận lỗi và giữ vé để khách thử lại."""
        user = db_session.query(User).filter(User.id == 1).first()

        booking = hold_seats(showtime_id=1, seat_ids=[1], user_id=user.id, db=db_session)

        # Mô phỏng thất bại qua VNPAY
        req = PaymentSandboxRequest(
            booking_id=booking.id,
            payment_method="VNPAY",
            status=PaymentStatusEnum.FAILED,
            failure_reason="Tài khoản không đủ số dư",
        )
        res = process_sandbox_payment(payload=req, current_user=user, db=db_session)

        assert res.status == "FAILED"
        assert "thất bại" in res.message.lower()

        # Trạng thái vé vẫn được giữ nguyên GIU_CHO để khách có thể thử lại
        db_session.refresh(booking)
        assert booking.status == "GIU_CHO"

        payment = db_session.query(Payment).filter(Payment.booking_id == booking.id).first()
        assert payment is not None
        assert payment.status == "FAILED"

    def test_sandbox_payment_rejects_unauthorized_user(self, db_session):
        """Không cho phép thanh toán đơn vé của người khác."""
        user1 = db_session.query(User).filter(User.id == 1).first()
        user2 = db_session.query(User).filter(User.id == 2).first()

        booking = hold_seats(showtime_id=1, seat_ids=[1], user_id=user1.id, db=db_session)

        req = PaymentSandboxRequest(
            booking_id=booking.id,
            payment_method="MOMO",
            status=PaymentStatusEnum.SUCCESS,
        )
        with pytest.raises(HTTPException) as exc_info:
            process_sandbox_payment(payload=req, current_user=user2, db=db_session)
        assert exc_info.value.status_code == 403
