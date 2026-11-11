"""
Unit tests cho T3C68CE: Model Booking & BookingSeat

Kiểm tra:
  1. Booking model có đủ 4 trạng thái
  2. BookingSeat có UniqueConstraint (showtime_id, seat_id)
  3. Schemas validate đúng
  4. BookingCreate giới hạn tối đa 8 ghế
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from pydantic import ValidationError

from app.schemas.booking import (
    BookingCreate,
    BookingResponse,
    BookingDetailResponse,
    BookingStatus,
    BookingStatusUpdate,
    BookingSeatCreate,
    BookingSeatResponse,
)
from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from sqlalchemy import UniqueConstraint, CheckConstraint


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestBookingModel:

    def test_booking_has_all_four_statuses_in_check_constraint(self):
        """CHECK constraint phải chứa đủ 4 trạng thái."""
        constraints = Booking.__table_args__
        check_texts = [str(c) for c in constraints if isinstance(c, CheckConstraint)]
        assert any("GIU_CHO" in t for t in check_texts)
        assert any("DA_THANH_TOAN" in t for t in check_texts)
        assert any("DA_HUY" in t for t in check_texts)
        assert any("HET_HAN" in t for t in check_texts)

    def test_booking_has_held_until_column(self):
        """Bảng bookings phải có cột held_until."""
        columns = {c.name for c in Booking.__table__.columns}
        assert "held_until" in columns

    def test_booking_has_updated_at_column(self):
        """Bảng bookings phải có cột updated_at."""
        columns = {c.name for c in Booking.__table__.columns}
        assert "updated_at" in columns

    def test_booking_has_booking_code_unique(self):
        """booking_code phải là unique."""
        col = Booking.__table__.columns["booking_code"]
        assert col.unique is True

    def test_booking_default_status_is_giu_cho(self):
        """Giá trị mặc định của status phải là GIU_CHO."""
        col = Booking.__table__.columns["status"]
        assert col.default.arg == "GIU_CHO"


class TestBookingSeatModel:

    def test_booking_seat_has_unique_constraint_showtime_seat(self):
        """Phải có UniqueConstraint trên (showtime_id, seat_id)."""
        constraints = BookingSeat.__table_args__
        unique_constraints = [c for c in constraints if isinstance(c, UniqueConstraint)]
        assert len(unique_constraints) == 1

        uc = unique_constraints[0]
        col_names = {c.name for c in uc.columns}
        assert "showtime_id" in col_names
        assert "seat_id" in col_names

    def test_booking_seat_has_showtime_id_column(self):
        """BookingSeat phải có cột showtime_id (FK trực tiếp để check unique)."""
        columns = {c.name for c in BookingSeat.__table__.columns}
        assert "showtime_id" in columns

    def test_booking_seat_has_price_column(self):
        """Phải có cột price (snapshot giá tại thời điểm đặt)."""
        columns = {c.name for c in BookingSeat.__table__.columns}
        assert "price" in columns


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestBookingStatus:

    def test_all_four_statuses_exist(self):
        statuses = {s.value for s in BookingStatus}
        assert statuses == {"GIU_CHO", "DA_THANH_TOAN", "DA_HUY", "HET_HAN"}


class TestBookingCreate:

    def test_valid_booking_create(self):
        data = BookingCreate(showtime_id=1, seat_ids=[1, 2, 3])
        assert data.showtime_id == 1
        assert len(data.seat_ids) == 3

    def test_seat_ids_minimum_one(self):
        """Phải có ít nhất 1 ghế."""
        with pytest.raises(ValidationError):
            BookingCreate(showtime_id=1, seat_ids=[])

    def test_seat_ids_maximum_eight(self):
        """Không được chọn quá 8 ghế."""
        with pytest.raises(ValidationError):
            BookingCreate(showtime_id=1, seat_ids=list(range(1, 10)))  # 9 ghế

    def test_exactly_eight_seats_is_valid(self):
        """Đúng 8 ghế phải hợp lệ."""
        data = BookingCreate(showtime_id=1, seat_ids=list(range(1, 9)))
        assert len(data.seat_ids) == 8

    def test_showtime_id_must_be_positive(self):
        with pytest.raises(ValidationError):
            BookingCreate(showtime_id=0, seat_ids=[1])


class TestBookingSeatCreate:

    def test_valid_seat_create(self):
        data = BookingSeatCreate(seat_id=5, price=Decimal("150000.00"))
        assert data.seat_id == 5
        assert data.price == Decimal("150000.00")

    def test_seat_id_must_be_positive(self):
        with pytest.raises(ValidationError):
            BookingSeatCreate(seat_id=0, price=Decimal("100000.00"))

    def test_price_must_be_non_negative(self):
        with pytest.raises(ValidationError):
            BookingSeatCreate(seat_id=1, price=Decimal("-1.00"))


class TestBookingStatusUpdate:

    def test_valid_status_update(self):
        data = BookingStatusUpdate(status=BookingStatus.DA_HUY)
        assert data.status == BookingStatus.DA_HUY

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            BookingStatusUpdate(status="INVALID_STATUS")


class TestBookingResponse:

    def test_booking_response_serializes_correctly(self):
        now = datetime.utcnow()
        response = BookingResponse(
            id=1,
            booking_code="BK-20241111-ABCD",
            user_id=10,
            showtime_id=5,
            total_price=Decimal("300000.00"),
            status=BookingStatus.GIU_CHO,
            held_until=now + timedelta(minutes=10),
            created_at=now,
            updated_at=now,
        )
        assert response.status == BookingStatus.GIU_CHO
        assert response.held_until is not None

    def test_held_until_can_be_null(self):
        """Sau khi thanh toán, held_until có thể là NULL."""
        now = datetime.utcnow()
        response = BookingResponse(
            id=2,
            booking_code="BK-20241111-EFGH",
            user_id=10,
            showtime_id=5,
            total_price=Decimal("300000.00"),
            status=BookingStatus.DA_THANH_TOAN,
            held_until=None,
            created_at=now,
            updated_at=now,
        )
        assert response.held_until is None
        assert response.status == BookingStatus.DA_THANH_TOAN
