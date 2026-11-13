"""
Service layer for Booking related operations.
Provides seat‑hold functionality (task T3C6902).
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.seat import Seat
from app.models.showtime import Showtime


def _calculate_total_price(seat_ids: List[int], db: Session) -> Decimal:
    """Tính tổng giá cho danh sách seat_id dựa trên giá snapshot hiện tại.
    Giả sử mô hình Seat có trường `price_multiplier` (1.0, 1.5, 2.0 ...) và Showtime có `price`.
    """
    total = Decimal("0")
    seats = db.query(Seat).filter(Seat.id.in_(seat_ids)).all()
    if len(seats) != len(seat_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Một hoặc nhiều seat_id không tồn tại",
        )
    # Lấy giá của suất chiếu (giá cơ bản) – sẽ được truyền từ hàm gọi.
    # Ở đây hàm gọi sẽ truyền showtime_price.
    return total  # placeholder – sẽ được tính trong hold_seats


def hold_seats(showtime_id: int, seat_ids: List[int], user_id: int, db: Session) -> Booking:
    """Tạo một Booking tạm thời (status=GIU_CHO) và giữ các ghế.
    - Kiểm tra số ghế ≤ 8.
    - Kiểm tra seat thuộc cùng showtime.
    - Sử dụng transaction để đảm bảo UNIQUE constraint (`showtime_id`, `seat_id`).
    """
    if len(seat_ids) > 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không được chọn quá 8 ghế trong một lần",
        )

    # Kiểm tra showtime tồn tại
    showtime = db.query(Showtime).filter(Showtime.id == showtime_id).first()
    if not showtime:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Showtime không tồn tại")

    # Kiểm tra các seat thuộc cùng phòng và cùng showtime
    seats = db.query(Seat).filter(Seat.id.in_(seat_ids)).all()
    if len(seats) != len(seat_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Một hoặc nhiều seat_id không tồn tại",
        )
    # Đảm bảo mọi seat thuộc cùng room của showtime
    room_id = showtime.room_id
    for seat in seats:
        if seat.room_id != room_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ghế không thuộc cùng phòng với suất chiếu",
            )

    # Tính total_price dựa trên giá cơ bản + multiplier (giả sử Seat có column `price_multiplier`)
    total_price = Decimal("0")
    for seat in seats:
        multiplier = getattr(seat, "price_multiplier", Decimal("1"))
        total_price += Decimal(showtime.price) * Decimal(multiplier)

    # Tạo Booking và BookingSeat trong một transaction
    try:
        with db.begin():
            booking = Booking(
                booking_code=f"BK-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{user_id}",
                user_id=user_id,
                showtime_id=showtime_id,
                total_price=total_price,
                status="GIU_CHO",
                held_until=datetime.utcnow() + timedelta(minutes=10),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(booking)
            db.flush()  # lấy booking.id

            # Thêm các BookingSeat – UNIQUE sẽ được kiểm tra ở cấp DB
            for seat in seats:
                booking_seat = BookingSeat(
                    booking_id=booking.id,
                    showtime_id=showtime_id,
                    seat_id=seat.id,
                    price=Decimal(showtime.price) * Decimal(getattr(seat, "price_multiplier", Decimal("1"))),
                )
                db.add(booking_seat)
    except IntegrityError as e:
        # Vi phạm UNIQUE => ghế đã được giữ hoặc đã đặt
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Một hoặc nhiều ghế đã được giữ hoặc đã đặt",
        ) from e

    # Đánh giá lại để trả về đối tượng Booking đã lưu (làm mới session)
    db.refresh(booking)
    return booking
