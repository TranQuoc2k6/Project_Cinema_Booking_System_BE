from decimal import Decimal

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.schemas.showtime import SeatStatusItem, ShowtimeSeatMapResponse


# Hệ số nhân giá theo loại ghế
SEAT_PRICE_MULTIPLIER: dict[str, Decimal] = {
    "standard": Decimal("1.0"),
    "vip": Decimal("1.5"),
    "couple": Decimal("2.0"),
}


def get_showtime_seat_map(
    showtime_id: int, db: Session
) -> ShowtimeSeatMapResponse:
    """
    Lấy sơ đồ ghế kèm trạng thái (available / held / booked) và giá
    cho một suất chiếu cụ thể.

    Quy tắc trạng thái:
      - booked  : booking.status == 'CONFIRMED'
      - held    : booking.status == 'PENDING'
      - available: không có booking nào hoặc booking đã CANCELLED
    """
    # 1. Kiểm tra suất chiếu tồn tại
    showtime: Showtime | None = (
        db.query(Showtime).filter(Showtime.id == showtime_id).first()
    )
    if showtime is None:
        return None  # Caller sẽ raise 404

    base_price: Decimal = Decimal(str(showtime.price))

    # 2. Lấy tất cả ghế của phòng chiếu, sắp xếp theo hàng → cột
    seats: list[Seat] = (
        db.query(Seat)
        .filter(Seat.room_id == showtime.room_id, Seat.is_active == True)
        .order_by(Seat.seat_row, Seat.seat_column)
        .all()
    )

    # 3. Truy vấn trạng thái ghế cho suất chiếu này
    #    Chỉ quan tâm booking PENDING hoặc CONFIRMED (bỏ CANCELLED)
    active_statuses = ("PENDING", "CONFIRMED")
    occupied: dict[int, str] = {}  # seat_id -> booking status

    rows_with_status = (
        db.query(BookingSeat.seat_id, Booking.status)
        .join(Booking, and_(
            BookingSeat.booking_id == Booking.id,
            Booking.showtime_id == showtime_id,
            Booking.status.in_(active_statuses),
        ))
        .all()
    )
    for seat_id, booking_status in rows_with_status:
        # Nếu một ghế có nhiều booking (edge case), ưu tiên CONFIRMED
        existing = occupied.get(seat_id)
        if existing != "CONFIRMED":
            occupied[seat_id] = booking_status

    # 4. Xây dựng danh sách ghế kèm trạng thái & giá
    seat_items: list[SeatStatusItem] = []
    for seat in seats:
        seat_type = seat.seat_type or "standard"
        multiplier = SEAT_PRICE_MULTIPLIER.get(seat_type, Decimal("1.0"))
        price = (base_price * multiplier).quantize(Decimal("0.01"))

        raw_status = occupied.get(seat.id)
        if raw_status == "CONFIRMED":
            status = "booked"
        elif raw_status == "PENDING":
            status = "held"
        else:
            status = "available"

        seat_items.append(
            SeatStatusItem(
                id=seat.id,
                seat_number=seat.seat_number,
                seat_row=seat.seat_row,
                seat_column=seat.seat_column,
                seat_type=seat_type,
                status=status,
                price=price,
            )
        )

    # 5. Nhóm ghế theo hàng để FE dễ render sơ đồ
    rows_map: dict[str, list[SeatStatusItem]] = {}
    for item in seat_items:
        rows_map.setdefault(item.seat_row, []).append(item)

    return ShowtimeSeatMapResponse(
        showtime_id=showtime_id,
        room_id=showtime.room_id,
        base_price=base_price,
        total_seats=len(seat_items),
        available_seats=sum(1 for s in seat_items if s.status == "available"),
        rows={row: seats_in_row for row, seats_in_row in rows_map.items()},
    )
