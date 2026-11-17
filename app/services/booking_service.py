"""
Service layer for Booking related operations.
Provides seat‑hold functionality (task T3C6902).
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc

from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.models.user import User
from app.models.movie import Movie
from app.models.room import Room
from app.models.cinema import Cinema
from app.models.payment import Payment


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


# ============================================================================
# API QUẢN TRỊ ĐƠN VÉ (ADMIN BOOKING MANAGEMENT)
# ============================================================================

def format_booking_admin(b: Booking) -> Dict[str, Any]:
    """Helper định dạng chi tiết một đơn vé cho Admin Portal."""
    st = b.showtime
    movie = st.movie if st else None
    room = st.room if st else None
    cinema = room.cinema if (room and hasattr(room, "cinema")) else None
    user = b.user

    # Trạng thái chuẩn hóa
    raw_status = (b.status or "").upper()
    if raw_status in ["DA_THANH_TOAN", "CONFIRMED", "SUCCESS"]:
        status_label = "confirmed"
    elif raw_status in ["GIU_CHO", "PENDING"]:
        status_label = "pending"
    else:
        status_label = "cancelled"

    # Danh sách ghế
    seats_list = []
    seat_details = []
    for bs in (b.booking_seats or []):
        seat_obj = bs.seat
        s_num = seat_obj.seat_number if seat_obj else f"Ghế #{bs.seat_id}"
        seats_list.append(s_num)
        seat_details.append({
            "id": bs.id,
            "seat_id": bs.seat_id,
            "seat_number": s_num,
            "seat_type": seat_obj.seat_type if seat_obj else "standard",
            "price": float(bs.price or 0)
        })

    # Phương thức thanh toán
    payment_method = "MOMO"
    payment_status = "success" if status_label == "confirmed" else status_label
    if b.payments and len(b.payments) > 0:
        p = b.payments[0]
        payment_method = p.payment_method or "Chuyển khoản"
        payment_status = p.status or payment_status

    showtime_str = st.start_time.strftime("%H:%M • %d/%m/%Y") if st and st.start_time else "Chưa xếp lịch"
    showtime_date = st.start_time.strftime("%Y-%m-%d") if st and st.start_time else ""

    return {
        "id": b.id,
        "code": b.booking_code,
        "booking_code": b.booking_code,
        "customer_name": user.full_name if user else "Khách vãng lai",
        "customer_phone": user.phone if (user and user.phone) else "",
        "customer_email": user.email if user else "",
        "user_id": b.user_id,
        "movie_id": movie.id if movie else None,
        "movie_title": movie.title if movie else "Chưa rõ phim",
        "movie_poster": movie.poster_url if movie else "",
        "cinema_id": cinema.id if cinema else None,
        "cinema_name": cinema.name if cinema else "Rạp chiếu phim",
        "room_id": room.id if room else None,
        "room_name": room.name if room else "Phòng chiếu",
        "room_type": room.room_type if room else "2D",
        "showtime_id": b.showtime_id,
        "showtime": showtime_str,
        "showtime_date": showtime_date,
        "showtime_start": st.start_time.isoformat() if st and st.start_time else None,
        "seats": seats_list,
        "seat_details": seat_details,
        "total_price": float(b.total_price or 0),
        "payment_method": payment_method,
        "payment_status": payment_status,
        "status": status_label,
        "raw_status": b.status,
        "booking_time": b.created_at.strftime("%Y-%m-%d %H:%M:%S") if b.created_at else "",
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


def admin_get_bookings(
    db: Session,
    page: int = 1,
    limit: int = 50,
    movie_id: Optional[int] = None,
    date_str: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """
    API lấy danh sách vé cho Quản trị viên:
    - Lọc theo phim (movie_id)
    - Lọc theo ngày chiếu hoặc ngày đặt vé (date_str: YYYY-MM-DD)
    - Lọc theo trạng thái (confirmed, pending, cancelled, all)
    - Tìm kiếm theo mã vé (booking_code) hoặc số điện thoại khách hàng (phone)
    """
    # Join Booking với Showtime và User để lọc linh hoạt
    query = db.query(Booking).join(Showtime, Booking.showtime_id == Showtime.id).join(User, Booking.user_id == User.id)

    # 1. Lọc theo phim (movie_id)
    if movie_id and movie_id > 0:
        query = query.filter(Showtime.movie_id == movie_id)

    # 2. Lọc theo ngày (YYYY-MM-DD)
    if date_str and date_str.strip():
        d = date_str.strip()
        # Tìm theo ngày chiếu hoặc ngày tạo đơn vé
        query = query.filter(
            or_(
                func.date(Showtime.start_time) == d,
                func.date(Booking.created_at) == d
            )
        )

    # 3. Lọc theo trạng thái
    if status_filter and status_filter.lower() != "all":
        st = status_filter.lower()
        if st in ["confirmed", "da_thanh_toan"]:
            query = query.filter(Booking.status.in_(["DA_THANH_TOAN", "confirmed", "CONFIRMED", "success"]))
        elif st in ["pending", "giu_cho"]:
            query = query.filter(Booking.status.in_(["GIU_CHO", "pending", "PENDING"]))
        elif st in ["cancelled", "da_huy", "het_han"]:
            query = query.filter(Booking.status.in_(["DA_HUY", "cancelled", "CANCELLED", "HET_HAN", "expired"]))

    # 4. Tìm kiếm theo mã vé hoặc Số điện thoại
    if search and search.strip():
        term = f"%{search.strip().lstrip('#')}%"
        query = query.filter(
            or_(
                Booking.booking_code.ilike(term),
                User.phone.ilike(term),
                User.full_name.ilike(term),
                User.email.ilike(term)
            )
        )

    total_records = query.count()
    offset_val = (page - 1) * limit
    bookings = query.order_by(desc(Booking.created_at)).offset(offset_val).limit(limit).all()

    items = [format_booking_admin(b) for b in bookings]
    total_pages = (total_records + limit - 1) // limit if limit > 0 else 1

    return {
        "status": "success",
        "total": total_records,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "items": items
    }


def admin_get_booking_by_id(db: Session, booking_id: int) -> Dict[str, Any]:
    """Xem chi tiết đơn vé cho Quản trị viên."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy đơn vé với ID #{booking_id}"
        )
    return {
        "status": "success",
        "data": format_booking_admin(booking)
    }


def admin_cancel_booking(db: Session, booking_id: int) -> Dict[str, Any]:
    """
    Hủy vé và giải phóng ghế:
    - Cập nhật trạng thái đơn vé sang 'DA_HUY'
    - Xóa các bản ghi BookingSeat tương ứng để giải phóng ghế cho suất chiếu
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy đơn vé với ID #{booking_id}"
        )

    if (booking.status or "").upper() in ["DA_HUY", "CANCELLED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn vé này đã được hủy trước đó."
        )

    # 1. Thu thập tên các ghế để thông báo
    released_seats = []
    for bs in booking.booking_seats:
        s_name = bs.seat.seat_number if bs.seat else f"ID {bs.seat_id}"
        released_seats.append(s_name)

    # 2. Xóa BookingSeat để giải phóng UNIQUE constraint ghế trong suất chiếu
    db.query(BookingSeat).filter(BookingSeat.booking_id == booking.id).delete(synchronize_session=False)

    # 3. Cập nhật trạng thái Booking sang DA_HUY
    booking.status = "DA_HUY"
    booking.held_until = None
    booking.updated_at = datetime.utcnow()

    # 4. Hủy các thanh toán liên quan nếu có
    for p in booking.payments:
        p.status = "cancelled"

    db.commit()
    db.refresh(booking)

    seat_info = ", ".join(released_seats) if released_seats else "Không có ghế"
    return {
        "status": "success",
        "message": f"Đã hủy thành công đơn vé #{booking.booking_code}! Ghế [{seat_info}] đã được giải phóng.",
        "booking_id": booking.id,
        "booking_code": booking.booking_code,
        "new_status": "cancelled",
        "released_seats": released_seats
    }
