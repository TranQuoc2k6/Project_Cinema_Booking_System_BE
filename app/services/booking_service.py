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


def get_user_bookings(user_id: int, status_filter: str | None, db: Session) -> list:
    """
    Lấy danh sách vé đã đặt của user (Task T3C5D0B).
    status_filter có thể là:
      - 'upcoming' (Sắp chiếu: status=DA_THANH_TOAN hoặc GIU_CHO và showtime.start_time > now)
      - 'watched'  (Đã xem: status=DA_THANH_TOAN và showtime.end_time <= now)
      - 'cancelled' (Đã hủy / Hết hạn: status IN ('DA_HUY', 'HET_HAN'))
      - Hoặc None / 'all' (Tất cả)
    """
    now = datetime.utcnow()
    query = db.query(Booking).filter(Booking.user_id == user_id)

    # Tự động cập nhật các booking GIU_CHO đã quá hạn held_until sang HET_HAN
    expired_bookings = query.filter(
        Booking.status == "GIU_CHO",
        Booking.held_until < now
    ).all()
    if expired_bookings:
        for eb in expired_bookings:
            eb.status = "HET_HAN"
        db.commit()

    # Query lại để lấy danh sách đầy đủ kèm quan hệ
    bookings = db.query(Booking).filter(Booking.user_id == user_id).order_by(Booking.created_at.desc()).all()

    result = []
    for b in bookings:
        st = b.showtime
        if not st:
            continue

        movie = st.movie
        room = st.room
        cinema = room.cinema if room else None

        # Xác định trạng thái thanh toán hiển thị
        if b.status == "DA_THANH_TOAN":
            payment_status = "PAID"
        elif b.status == "GIU_CHO":
            payment_status = "PENDING"
        elif b.status == "DA_HUY":
            payment_status = "CANCELLED"
        else:
            payment_status = "EXPIRED"

        # Phân loại tab
        # 1. 'upcoming': Suất chiếu sắp tới & chưa hủy/hết hạn
        is_upcoming = (b.status in ("DA_THANH_TOAN", "GIU_CHO")) and (st.start_time > now)
        # 2. 'watched': Đã thanh toán và suất chiếu đã kết thúc hoặc bắt đầu
        is_watched = (b.status == "DA_THANH_TOAN") and (st.start_time <= now)
        # 3. 'cancelled': Đã hủy hoặc hết hạn
        is_cancelled = b.status in ("DA_HUY", "HET_HAN")

        if status_filter == "upcoming" and not is_upcoming:
            continue
        elif status_filter == "watched" and not is_watched:
            continue
        elif status_filter == "cancelled" and not is_cancelled:
            continue

        # Danh sách ghế
        seats_data = []
        for bs in b.booking_seats:
            seat_obj = bs.seat
            seats_data.append({
                "id": bs.id,
                "seat_id": bs.seat_id,
                "seat_number": seat_obj.seat_number if seat_obj else f"Ghế {bs.seat_id}",
                "seat_row": seat_obj.seat_row if seat_obj else None,
                "seat_column": seat_obj.seat_column if seat_obj else None,
                "seat_type": seat_obj.seat_type if seat_obj else "standard",
                "price": bs.price,
            })

        result.append({
            "id": b.id,
            "booking_code": b.booking_code,
            "status": b.status,
            "payment_status": payment_status,
            "total_price": b.total_price,
            "held_until": b.held_until,
            "created_at": b.created_at,
            "showtime": {
                "id": st.id,
                "start_time": st.start_time,
                "end_time": st.end_time,
                "room_name": room.name if room else "Phòng chiếu",
                "room_type": room.room_type if room else "2D",
                "cinema": {
                    "id": cinema.id if cinema else 0,
                    "name": cinema.name if cinema else "Rạp chiếu phim",
                    "address": cinema.address if cinema else None,
                    "city": cinema.city if cinema else None,
                },
                "movie": {
                    "id": movie.id if movie else 0,
                    "title": movie.title if movie else "Tên phim",
                    "poster_url": movie.poster_url if movie else None,
                    "duration_minutes": movie.duration_minutes if movie else 120,
                },
            },
            "seats": seats_data,
        })

    return result
