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


# Hệ số nhân giá theo loại ghế (chuẩn toàn hệ thống)
SEAT_PRICE_MULTIPLIER: dict[str, Decimal] = {
    "standard": Decimal("1.0"),
    "vip": Decimal("1.5"),
    "couple": Decimal("2.0"),
}


def get_seat_multiplier(seat: Optional[Seat]) -> Decimal:
    """Lấy hệ số nhân giá ghế an toàn (ưu tiên price_multiplier từ DB nếu có)."""
    if not seat:
        return Decimal("1.0")
    m = getattr(seat, "price_multiplier", None)
    if m is not None:
        try:
            return Decimal(str(m))
        except Exception:
            pass
    stype = (seat.seat_type or "standard").lower()
    return SEAT_PRICE_MULTIPLIER.get(stype, Decimal("1.0"))


def clean_expired_holds(db: Session) -> dict:
    """
    Tự động chuyển giữ chỗ quá hạn sang HET_HAN để trả ghế (Task T3C6CE6).
    
    Quy trình:
      1. Tìm tất cả các booking có status in ('GIU_CHO', 'PENDING') và held_until <= now.
      2. Thu thập danh sách ID của các booking quá hạn.
      3. Xóa các BookingSeat tương ứng để giải phóng UNIQUE constraint (showtime_id, seat_id),
         giúp trả ghế về trạng thái trống (available) cho các khách hàng khác.
      4. Cập nhật booking.status sang 'HET_HAN', held_until = None, updated_at = now.
      5. Đánh dấu payment pending tương ứng sang EXPIRED (nếu có).
      6. Commit transaction và trả về thống kê.
    """
    now = datetime.utcnow()
    expired_bookings = (
        db.query(Booking)
        .filter(
            Booking.status.in_(["GIU_CHO", "PENDING"]),
            Booking.held_until.isnot(None),
            Booking.held_until <= now,
        )
        .all()
    )

    if not expired_bookings:
        return {
            "expired_bookings_count": 0,
            "released_seats_count": 0,
            "message": "Không có đơn giữ chỗ nào quá hạn.",
        }

    expired_ids = [b.id for b in expired_bookings]

    # Xóa BookingSeat để giải phóng ghế về trạng thái trống
    deleted_seats_count = (
        db.query(BookingSeat)
        .filter(BookingSeat.booking_id.in_(expired_ids))
        .delete(synchronize_session=False)
    )

    # Cập nhật trạng thái Booking sang HET_HAN
    for b in expired_bookings:
        b.status = "HET_HAN"
        b.held_until = None
        b.updated_at = now
        for p in b.payments:
            if (p.status or "").upper() == "PENDING":
                p.status = "EXPIRED"

    db.commit()

    return {
        "expired_bookings_count": len(expired_bookings),
        "released_seats_count": deleted_seats_count,
        "message": f"Đã giải phóng {deleted_seats_count} ghế từ {len(expired_bookings)} đơn giữ chỗ quá hạn (chuyển sang HET_HAN).",
    }


def hold_seats(showtime_id: int, seat_ids: List[int], user_id: int, db: Session) -> Booking:
    """Tạo một Booking tạm thời (status=GIU_CHO) và giữ các ghế.
    - Dọn dẹp các đơn giữ chỗ quá hạn trước.
    - Kiểm tra số ghế ≤ 8.
    - Kiểm tra seat thuộc cùng showtime.
    - Sử dụng transaction để đảm bảo UNIQUE constraint (`showtime_id`, `seat_id`).
    """
    # 0. Tự động giải phóng các ghế giữ chỗ quá hạn trước khi kiểm tra
    clean_expired_holds(db)

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

    # Tính total_price dựa trên giá cơ bản suất chiếu * multiplier của từng ghế
    base_price = Decimal(str(showtime.price))
    total_price = Decimal("0")
    for seat in seats:
        mult = get_seat_multiplier(seat)
        total_price += (base_price * mult).quantize(Decimal("0.01"))

    # Tạo Booking và BookingSeat trong một transaction an toàn
    try:
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
            mult = get_seat_multiplier(seat)
            seat_price = (base_price * mult).quantize(Decimal("0.01"))
            booking_seat = BookingSeat(
                booking_id=booking.id,
                showtime_id=showtime_id,
                seat_id=seat.id,
                price=seat_price,
            )
            db.add(booking_seat)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # Vi phạm UNIQUE => ghế đã được giữ hoặc đã đặt
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Một hoặc nhiều ghế đã được giữ hoặc đã đặt",
        ) from e
    except Exception:
        db.rollback()
        raise

    # Đánh giá lại để trả về đối tượng Booking đã lưu (làm mới session)
    db.refresh(booking)
    return booking


def confirm_booking(
    db: Session,
    user: User,
    booking_id: Optional[int] = None,
    booking_code: Optional[str] = None,
    payment_method: str = "MOMO",
    transaction_id: Optional[str] = None,
) -> dict:
    """
    Xác nhận đặt vé từ ghế đang giữ, tính lại tiền ở server;
    tự chuyển giữ chỗ quá hạn sang HET_HAN để trả ghế (Task T3C6CE6).
    """
    # 1. Tự động giải phóng các ghế giữ chỗ quá hạn
    clean_expired_holds(db)

    # 2. Tìm đơn đặt vé
    query = db.query(Booking)
    if booking_id:
        booking = query.filter(Booking.id == booking_id).first()
    elif booking_code:
        booking = query.filter(Booking.booking_code == booking_code.strip()).first()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp booking_id hoặc booking_code để xác nhận đặt vé.",
        )

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn đặt vé cần xác nhận.",
        )

    # 3. Phân quyền: Người dùng chỉ được xác nhận vé của mình (trừ khi là ADMIN)
    user_role = (user.role.name if user.role else "").upper()
    if booking.user_id != user.id and user_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xác nhận đơn vé của người khác.",
        )

    # 4. Kiểm tra trạng thái hiện tại
    current_status = (booking.status or "").upper()
    if current_status == "DA_THANH_TOAN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn vé này đã được thanh toán và xác nhận thành công trước đó.",
        )
    if current_status == "DA_HUY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn vé này đã bị hủy, không thể xác nhận đặt vé.",
        )
    if current_status == "HET_HAN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn vé này đã hết hạn giữ chỗ (HET_HAN). Ghế đã được trả lại. Vui lòng chọn lại ghế.",
        )

    # 5. Kiểm tra thời hạn giữ chỗ (held_until)
    now = datetime.utcnow()
    if booking.held_until and booking.held_until < now:
        # Quá hạn -> tự động giải phóng ghế sang HET_HAN
        db.query(BookingSeat).filter(BookingSeat.booking_id == booking.id).delete(synchronize_session=False)
        booking.status = "HET_HAN"
        booking.held_until = None
        booking.updated_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thời gian giữ chỗ 10 phút của đơn vé đã quá hạn. Hệ thống đã tự động chuyển sang HET_HAN và trả lại ghế.",
        )

    # 6. TÍNH LẠI TIỀN Ở SERVER (Server Price Recalculation)
    showtime = booking.showtime
    if not showtime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suất chiếu của đơn vé không còn tồn tại.",
        )

    base_price = Decimal(str(showtime.price))
    if not booking.booking_seats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn vé không có ghế nào được giữ để xác nhận.",
        )

    server_total_price = Decimal("0")
    for bs in booking.booking_seats:
        seat = bs.seat
        mult = get_seat_multiplier(seat)
        calculated_seat_price = (base_price * mult).quantize(Decimal("0.01"))
        bs.price = calculated_seat_price
        server_total_price += calculated_seat_price

    # Cập nhật tổng tiền chuẩn xác được tính toán lại tại Server
    booking.total_price = server_total_price

    # 7. Cập nhật trạng thái Booking sang DA_THANH_TOAN và giải phóng hạn giữ chỗ
    booking.status = "DA_THANH_TOAN"
    booking.held_until = None
    booking.updated_at = now

    # 8. Ghi nhận thông tin thanh toán (Payment)
    actual_txn_id = transaction_id or f"TXN-{booking.booking_code}-{int(now.timestamp())}"
    actual_method = (payment_method or "MOMO").upper()

    existing_payment = (
        db.query(Payment)
        .filter(Payment.booking_id == booking.id)
        .first()
    )
    if existing_payment:
        existing_payment.amount = server_total_price
        existing_payment.payment_method = actual_method
        existing_payment.status = "SUCCESS"
        existing_payment.transaction_id = actual_txn_id
        existing_payment.payment_time = now
        payment_record = existing_payment
    else:
        payment_record = Payment(
            booking_id=booking.id,
            amount=server_total_price,
            payment_method=actual_method,
            status="SUCCESS",
            transaction_id=actual_txn_id,
            payment_time=now,
        )
        db.add(payment_record)

    db.commit()
    db.refresh(booking)

    return {
        "success": True,
        "message": f"Xác nhận đặt vé #{booking.booking_code} thành công!",
        "booking": booking,
        "recalculated_price": server_total_price,
        "payment_id": payment_record.id,
        "payment_status": payment_record.status,
    }



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
