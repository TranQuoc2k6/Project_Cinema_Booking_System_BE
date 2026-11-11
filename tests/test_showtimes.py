"""
Unit tests cho T3C68E8: GET /api/showtimes/{id}/seats
Kiểm tra logic phân loại trạng thái ghế và tính giá.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.services.showtime_service import get_showtime_seat_map, SEAT_PRICE_MULTIPLIER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_seat(seat_id, seat_row, seat_column, seat_type="standard", is_active=True):
    seat = MagicMock()
    seat.id = seat_id
    seat.seat_number = f"{seat_row}{seat_column:02d}"
    seat.seat_row = seat_row
    seat.seat_column = seat_column
    seat.seat_type = seat_type
    seat.is_active = is_active
    return seat


def _make_showtime(showtime_id=1, room_id=10, price="100000.00"):
    st = MagicMock()
    st.id = showtime_id
    st.room_id = room_id
    st.price = Decimal(price)
    return st


def _build_db(showtime, seats, occupied_rows):
    """
    Xây dựng mock DB session trả về đúng kết quả cho từng query.
    occupied_rows: list of (seat_id, booking_status)
    """
    db = MagicMock()

    # Query 1: showtime
    q_showtime = MagicMock()
    q_showtime.filter.return_value.first.return_value = showtime

    # Query 2: seats
    q_seats = MagicMock()
    q_seats.filter.return_value.order_by.return_value.all.return_value = seats

    # Query 3: booking_seat join
    q_bs = MagicMock()
    q_bs.join.return_value.all.return_value = occupied_rows

    # side_effect as a list: each call to db.query() consumes the next item
    call_results = [q_showtime, q_seats, q_bs]
    _iter = iter(call_results)
    db.query.side_effect = lambda *args, **kwargs: next(_iter)

    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestShowtimeSeatMap:

    def test_404_when_showtime_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = get_showtime_seat_map(showtime_id=999, db=db)
        assert result is None

    def test_all_available_when_no_bookings(self):
        showtime = _make_showtime(showtime_id=1, room_id=5, price="80000.00")
        seats = [
            _make_seat(1, "A", 1, "standard"),
            _make_seat(2, "A", 2, "vip"),
        ]
        db = _build_db(showtime, seats, occupied_rows=[])
        result = get_showtime_seat_map(showtime_id=1, db=db)

        assert result is not None
        assert result.total_seats == 2
        assert result.available_seats == 2
        for row_seats in result.rows.values():
            for seat in row_seats:
                assert seat.status.value == "available"

    def test_held_seat_from_pending_booking(self):
        showtime = _make_showtime(price="100000.00")
        seats = [_make_seat(10, "B", 3, "standard")]
        db = _build_db(showtime, seats, occupied_rows=[(10, "PENDING")])
        result = get_showtime_seat_map(showtime_id=1, db=db)

        seat = result.rows["B"][0]
        assert seat.status.value == "held"
        assert result.available_seats == 0

    def test_booked_seat_from_confirmed_booking(self):
        showtime = _make_showtime(price="100000.00")
        seats = [_make_seat(20, "C", 1, "standard")]
        db = _build_db(showtime, seats, occupied_rows=[(20, "CONFIRMED")])
        result = get_showtime_seat_map(showtime_id=1, db=db)

        seat = result.rows["C"][0]
        assert seat.status.value == "booked"

    def test_confirmed_takes_priority_over_pending(self):
        """Nếu cùng ghế có 2 booking, CONFIRMED ưu tiên hơn PENDING."""
        showtime = _make_showtime(price="100000.00")
        seats = [_make_seat(30, "D", 1, "standard")]
        # Edge case: 2 rows cho cùng seat_id
        db = _build_db(showtime, seats, occupied_rows=[(30, "PENDING"), (30, "CONFIRMED")])
        result = get_showtime_seat_map(showtime_id=1, db=db)

        seat = result.rows["D"][0]
        assert seat.status.value == "booked"

    def test_price_calculation_standard(self):
        showtime = _make_showtime(price="100000.00")
        seats = [_make_seat(1, "A", 1, "standard")]
        db = _build_db(showtime, seats, occupied_rows=[])
        result = get_showtime_seat_map(showtime_id=1, db=db)
        assert result.rows["A"][0].price == Decimal("100000.00")

    def test_price_calculation_vip(self):
        showtime = _make_showtime(price="100000.00")
        seats = [_make_seat(2, "A", 2, "vip")]
        db = _build_db(showtime, seats, occupied_rows=[])
        result = get_showtime_seat_map(showtime_id=1, db=db)
        # VIP x1.5
        assert result.rows["A"][0].price == Decimal("150000.00")

    def test_price_calculation_couple(self):
        showtime = _make_showtime(price="100000.00")
        seats = [_make_seat(3, "A", 3, "couple")]
        db = _build_db(showtime, seats, occupied_rows=[])
        result = get_showtime_seat_map(showtime_id=1, db=db)
        # Couple x2.0
        assert result.rows["A"][0].price == Decimal("200000.00")

    def test_rows_grouping(self):
        showtime = _make_showtime()
        seats = [
            _make_seat(1, "A", 1),
            _make_seat(2, "A", 2),
            _make_seat(3, "B", 1),
        ]
        db = _build_db(showtime, seats, occupied_rows=[])
        result = get_showtime_seat_map(showtime_id=1, db=db)

        assert "A" in result.rows
        assert "B" in result.rows
        assert len(result.rows["A"]) == 2
        assert len(result.rows["B"]) == 1

    def test_seat_map_response_fields(self):
        showtime = _make_showtime(showtime_id=5, room_id=7, price="120000.00")
        seats = [_make_seat(99, "Z", 1, "standard")]
        db = _build_db(showtime, seats, occupied_rows=[])
        result = get_showtime_seat_map(showtime_id=5, db=db)

        assert result.showtime_id == 5
        assert result.room_id == 7
        assert result.base_price == Decimal("120000.00")
