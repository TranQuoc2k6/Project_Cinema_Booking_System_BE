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
from app.models.payment import Payment
from app.core.pricing import calculate_seat_price


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


def validate_seat_adjacency_and_gaps(
    db: Session,
    showtime_id: int,
    seat_ids: List[int],
    room_id: int,
) -> None:
    """
    Quy định 11: Khi đặt vé, vé chỉ được thanh toán khi 2 vé được đặt cạnh nhau và không được có ghế trống xen giữa.
    Bao gồm các nguyên tắc nghiệp vụ rạp chiếu:
      1. Khi khách đặt 2 vé: 2 vé này bắt buộc phải nằm trên cùng một hàng (seat_row)
         và phải nằm cạnh nhau (seat_column liền kề), không được chọn ở hai hàng khác nhau
         và không được có ghế trống xen giữa.
      2. Trong cùng một hàng: Nếu khách chọn từ 2 vé trở lên, các vé đó phải được đặt
         liền kề nhau, không được có ghế trống xen giữa các ghế được chọn (ví dụ chọn A1, A3
         mà để trống A2 ở giữa là không hợp lệ).
      3. Quy tắc không để lại 1 ghế trống đơn độc xen giữa (No isolated single empty seat):
         Trên một hàng, sau khi chọn các ghế, không được để lại đúng 1 ghế trống xen giữa
         ghế đang chọn với ghế đã bán / đang giữ, hoặc giữa ghế đang chọn với đầu/cuối dãy.
    """
    if not seat_ids:
        return

    # Lấy toàn bộ danh sách ghế của phòng chiếu theo thứ tự hàng & cột
    room_seats = (
        db.query(Seat)
        .filter(Seat.room_id == room_id, Seat.is_active != False)
        .order_by(Seat.seat_row, Seat.seat_column)
        .all()
    )
    if not room_seats:
        return

    seat_map_by_id = {s.id: s for s in room_seats}
    selected_seats = [seat_map_by_id[sid] for sid in seat_ids if sid in seat_map_by_id]
    if len(selected_seats) != len(seat_ids):
        return

    # Gom nhóm ghế của phòng theo từng hàng
    seats_by_row: Dict[str, List[Seat]] = {}
    for s in room_seats:
        seats_by_row.setdefault(s.seat_row, []).append(s)
    for r in seats_by_row:
        seats_by_row[r].sort(key=lambda x: x.seat_column)

    # Gom nhóm các ghế khách chọn theo từng hàng
    selected_by_row: Dict[str, List[Seat]] = {}
    for s in selected_seats:
        selected_by_row.setdefault(s.seat_row, []).append(s)

    # 1. KIỂM TRA ĐẶT 2 VÉ: Bắt buộc cùng một hàng và cạnh nhau, không có ghế trống xen giữa
    if len(selected_seats) == 2:
        rows = list(selected_by_row.keys())
        if len(rows) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quy định đặt vé: Khi đặt 2 vé, 2 vé phải được đặt cạnh nhau trên cùng một hàng (không được chọn ở hai hàng khác nhau).",
            )
        row_name = rows[0]
        row_all_seats = seats_by_row[row_name]
        s1, s2 = sorted(selected_seats, key=lambda x: x.seat_column)
        idx1 = next((i for i, s in enumerate(row_all_seats) if s.id == s1.id), -1)
        idx2 = next((i for i, s in enumerate(row_all_seats) if s.id == s2.id), -1)
        if idx2 != idx1 + 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quy định đặt vé: 2 vé [{s1.seat_number}, {s2.seat_number}] phải được đặt cạnh nhau và không được có ghế trống xen giữa.",
            )

    # 2. KIỂM TRA TRONG CÙNG HÀNG: Các ghế khách chọn phải liền kề nhau, không có ghế trống xen giữa
    for row_name, sel_in_row in selected_by_row.items():
        if len(sel_in_row) >= 2:
            row_all_seats = seats_by_row[row_name]
            sel_sorted = sorted(sel_in_row, key=lambda x: x.seat_column)
            indices = [
                next(i for i, s in enumerate(row_all_seats) if s.id == sel.id)
                for sel in sel_sorted
            ]
            for k in range(len(indices) - 1):
                if indices[k + 1] != indices[k] + 1:
                    gap_seats = [row_all_seats[j].seat_number for j in range(indices[k] + 1, indices[k + 1])]
                    gap_str = ", ".join(gap_seats)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Quy định đặt vé tại hàng {row_name}: Các ghế được chọn phải liền kề nhau, không được có ghế trống xen giữa ({gap_str}).",
                    )


def hold_seats(
    showtime_id: int,
    seat_ids: List[int],
    user_id: int,
    db: Session,
    combos: Optional[List[Any]] = None,
) -> Booking:
    """Tạo một Booking tạm thời (status=GIU_CHO) và giữ các ghế.
    - Dọn dẹp các đơn giữ chỗ quá hạn trước.
    - Kiểm tra số ghế ≤ 8.
    - Kiểm tra suất chiếu còn hiệu lực và chưa bắt đầu (Rule 2).
    - Kiểm tra phim đang được phép bán vé (Rule 1).
    - Kiểm tra seat thuộc cùng showtime và còn hoạt động (Rule 3 & 4).
    - Kiểm tra ghế chưa có người đặt/giữ (Rule 4 & 10).
    - Kiểm tra 2 vé cạnh nhau và không để ghế trống xen giữa (Rule 11).
    - Hỗ trợ chọn mua kèm combo bắp nước (Task T3C72E6).
    - Sử dụng transaction để đảm bảo UNIQUE constraint (`showtime_id`, `seat_id`).
    """
    # 0. Tự động giải phóng các ghế giữ chỗ quá hạn trước khi kiểm tra
    clean_expired_holds(db)

    if len(seat_ids) > 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không được chọn quá 8 ghế trong một lần",
        )

    # 1. Kiểm tra showtime tồn tại
    showtime = db.query(Showtime).filter(Showtime.id == showtime_id).first()
    if not showtime:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Showtime không tồn tại")

    # Rule 2: Chỉ được đặt vé cho suất chiếu còn hiệu lực và chưa bắt đầu
    now_utc = datetime.utcnow()
    if isinstance(showtime.start_time, datetime) and showtime.start_time <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suất chiếu đã bắt đầu hoặc đã qua thời gian đặt vé. Vui lòng chọn suất chiếu khác.",
        )

    # Rule 1: Khách hàng phải chọn phim đang được phép bán vé
    if showtime.movie:
        movie_status = (showtime.movie.status or "").upper()
        if movie_status in ["ENDED", "NGUNG_CHIEU"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phim này đã ngừng chiếu, hiện không được phép bán vé.",
            )
        if movie_status == "COMING_SOON" and showtime.movie.release_date and showtime.start_time and showtime.movie.release_date > showtime.start_time.date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phim chưa đến ngày khởi chiếu chính thức, chưa mở bán vé.",
            )

    # Rule 3 & 4: Kiểm tra các seat thuộc cùng phòng và cùng showtime
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
        if seat.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ghế {seat.seat_number} đang tạm ngừng hoạt động hoặc bảo trì, không thể chọn.",
            )

    # Rule 4 & 10: Kiểm tra ghế đã được giữ hoặc đã đặt trước khi tạo booking
    occupied_seats = (
        db.query(BookingSeat.seat_id, Seat.seat_number)
        .join(Seat, BookingSeat.seat_id == Seat.id)
        .join(Booking, BookingSeat.booking_id == Booking.id)
        .filter(
            BookingSeat.showtime_id == showtime_id,
            BookingSeat.seat_id.in_(seat_ids),
            Booking.status.in_(["GIU_CHO", "PENDING", "DA_THANH_TOAN", "CONFIRMED"]),
        )
        .all()
    )
    if occupied_seats:
        occupied_names = ", ".join([s[1] for s in occupied_seats])
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Một hoặc nhiều ghế [{occupied_names}] đã được giữ hoặc đã đặt bởi khách hàng khác.",
        )

    # Rule 11: Kiểm tra quy định đặt 2 vé cạnh nhau và không có ghế trống xen giữa
    validate_seat_adjacency_and_gaps(db=db, showtime_id=showtime_id, seat_ids=seat_ids, room_id=room_id)

    # Tính total_price dựa trên giá cơ bản suất chiếu, phụ thu cuối tuần/giờ vàng & multiplier của từng ghế
    base_price = Decimal(str(showtime.price))
    st_start = showtime.start_time if isinstance(getattr(showtime, "start_time", None), datetime) else None
    seat_prices_map = {}
    total_price = Decimal("0")
    for seat in seats:
        seat_price = calculate_seat_price(
            base_price=base_price,
            seat_type=seat.seat_type,
            showtime_start=st_start,
        )
        seat_prices_map[seat.id] = seat_price
        total_price += seat_price

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
            seat_price = seat_prices_map[seat.id]
            booking_seat = BookingSeat(
                booking_id=booking.id,
                showtime_id=showtime_id,
                seat_id=seat.id,
                price=seat_price,
            )
            db.add(booking_seat)

        # Lưu các combo bắp nước nếu khách có chọn (Task T3C72E6)
        if combos:
            from app.services.combo_service import save_booking_combos
            combo_total = save_booking_combos(db, booking.id, combos)
            total_price += combo_total
            booking.total_price = total_price

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
    combos: Optional[List[Any]] = None,
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

    # Rule 2: Suất chiếu còn hiệu lực và chưa bắt đầu
    if showtime.start_time and showtime.start_time <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suất chiếu đã bắt đầu, không thể hoàn tất thanh toán vé.",
        )

    # Rule 1: Phim đang được phép bán vé
    if showtime.movie:
        movie_status = (showtime.movie.status or "").upper()
        if movie_status in ["ENDED", "NGUNG_CHIEU"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phim này đã ngừng chiếu, không thể xác nhận đặt vé.",
            )

    base_price = Decimal(str(showtime.price))
    st_start = showtime.start_time if isinstance(getattr(showtime, "start_time", None), datetime) else None
    if not booking.booking_seats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn vé không có ghế nào được giữ để xác nhận.",
        )

    server_total_price = Decimal("0")
    for bs in booking.booking_seats:
        seat = bs.seat
        stype = seat.seat_type if seat else "standard"
        calculated_seat_price = calculate_seat_price(
            base_price=base_price,
            seat_type=stype,
            showtime_start=st_start,
        )
        bs.price = calculated_seat_price
        server_total_price += calculated_seat_price

    # Cộng thêm tiền combo bắp nước nếu có (Task T3C72E6)
    if combos is not None:
        from app.services.combo_service import save_booking_combos
        combos_total = save_booking_combos(db, booking.id, combos)
        server_total_price += combos_total
    else:
        for bc in getattr(booking, "booking_combos", []):
            server_total_price += Decimal(str(bc.price)) * Decimal(bc.quantity)

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



def _get_effective_ref_now(start_time: Optional[datetime], default_now: Optional[datetime] = None) -> datetime:
    """
    Xác định thời điểm hiện tại tương thích chính xác cả môi trường UTC và Giờ địa phương (GMT+7).
    - Nếu start_time có timezone, sử dụng datetime.now(tzinfo).
    - Nếu naive: tự động nhận diện mốc thời gian chuẩn để đảm bảo đúng quy tắc
      'Hủy vé trước 2 tiếng phim bắt đầu'.
    """
    if not start_time:
        return default_now or datetime.utcnow()
    if start_time.tzinfo is not None:
        return datetime.now(start_time.tzinfo)

    now_utc = default_now or datetime.utcnow()
    now_local = datetime.now()

    delta_loc = (start_time - now_local).total_seconds()
    delta_u = (start_time - now_utc).total_seconds()

    if 0 <= delta_loc < delta_u:
        return now_local
    elif delta_u < 0 and delta_loc < 0:
        return now_local if abs(delta_loc) < abs(delta_u) else now_utc
    elif delta_loc < 0 <= delta_u:
        return now_utc
    else:
        return now_local if abs(delta_loc) < abs(delta_u) else now_utc


def format_ticket_response(b: Booking, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Helper định dạng chi tiết vé điện tử đầy đủ kèm cờ hủy vé (Task T3C6D1A)."""
    if now is None:
        now = datetime.utcnow()
    st = b.showtime
    movie = st.movie if st else None
    room = st.room if st else None
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

    # Kiểm tra điều kiện huỷ vé (Task T3C6D1A: khách huỷ vé trước giờ chiếu ít nhất 2 tiếng)
    st_start = st.start_time if (st and isinstance(st.start_time, datetime)) else None
    cancel_deadline = (st_start - timedelta(hours=2)) if st_start else None
    can_cancel = False
    cancel_reason = None

    ref_now = _get_effective_ref_now(st_start, default_now=now)

    if b.status in ("DA_THANH_TOAN", "GIU_CHO"):
        if cancel_deadline and ref_now <= cancel_deadline:
            can_cancel = True
        else:
            if cancel_deadline and ref_now > cancel_deadline:
                if st_start and st_start <= ref_now:
                    cancel_reason = "Suất chiếu đã bắt đầu hoặc đã qua"
                else:
                    cancel_reason = "Đã quá hạn hủy (chỉ hủy được trước giờ chiếu ít nhất 2 tiếng)"
            else:
                cancel_reason = "Không xác định được thời gian suất chiếu"
    elif b.status == "DA_HUY":
        cancel_reason = "Vé đã được hủy"
    elif b.status == "HET_HAN":
        cancel_reason = "Đơn giữ chỗ đã hết hạn"

    # Danh sách ghế
    seats_data = []
    for bs in b.booking_seats:
        seat_obj = bs.seat
        ticket_code = getattr(bs, "ticket_code", None) or f"TK-{b.booking_code}-{seat_obj.seat_number if seat_obj else bs.seat_id}"
        seats_data.append({
            "id": bs.id,
            "seat_id": bs.seat_id,
            "seat_number": seat_obj.seat_number if seat_obj else f"Ghế {bs.seat_id}",
            "seat_row": seat_obj.seat_row if seat_obj else None,
            "seat_column": seat_obj.seat_column if seat_obj else None,
            "seat_type": seat_obj.seat_type if seat_obj else "standard",
            "price": bs.price,
            "ticket_code": ticket_code,
        })

    return {
        "id": b.id,
        "booking_code": b.booking_code,
        "status": b.status,
        "payment_status": payment_status,
        "total_price": b.total_price,
        "held_until": b.held_until,
        "created_at": b.created_at,
        "showtime": {
            "id": st.id if st else 0,
            "start_time": st.start_time if st else now,
            "end_time": st.end_time if st else now,
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
        "can_cancel": can_cancel,
        "cancel_deadline": cancel_deadline,
        "cancel_reason": cancel_reason,
        "is_checked_in": getattr(b, "is_checked_in", False) or False,
        "checked_in_at": getattr(b, "checked_in_at", None),
        "combos": [
            {
                "id": bc.id,
                "combo_id": bc.combo_id,
                "name": bc.combo.name if bc.combo else f"Combo #{bc.combo_id}",
                "quantity": bc.quantity,
                "price": Decimal(str(bc.price)),
                "total_price": Decimal(str(bc.price)) * Decimal(bc.quantity),
                "image_url": bc.combo.image_url if bc.combo else None,
            }
            for bc in getattr(b, "booking_combos", [])
        ],
    }


def get_user_bookings(user_id: int, status_filter: str | None, db: Session) -> list:
    """
    Lấy danh sách vé đã đặt của user (Task T3C5D0B & T3C6D1A).
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

        # Phân loại tab
        ref_st_now = _get_effective_ref_now(st.start_time, default_now=now)
        # 1. 'upcoming': Suất chiếu sắp tới & chưa hủy/hết hạn
        is_upcoming = (b.status in ("DA_THANH_TOAN", "GIU_CHO")) and (st.start_time > ref_st_now)
        # 2. 'watched': Đã thanh toán và suất chiếu đã kết thúc hoặc bắt đầu
        is_watched = (b.status == "DA_THANH_TOAN") and (st.start_time <= ref_st_now)
        # 3. 'cancelled': Đã hủy hoặc hết hạn
        is_cancelled = b.status in ("DA_HUY", "HET_HAN")

        if status_filter == "upcoming" and not is_upcoming:
            continue
        elif status_filter == "watched" and not is_watched:
            continue
        elif status_filter == "cancelled" and not is_cancelled:
            continue

        result.append(format_ticket_response(b, now))

    return result


def user_cancel_booking(db: Session, user: User, booking_id: int) -> Dict[str, Any]:
    """
    Khách hàng hủy vé xem phim và giải phóng ghế (Task T3C6D1A).
    
    Quy định:
      - Khách hủy được vé trước giờ chiếu 2 tiếng (trả ghế).
      - Đơn vé phải thuộc sở hữu của chính khách hàng đó.
      - Vé chưa bị hủy trước đó hoặc chưa hết hạn giữ chỗ.
      
    Hành động:
      1. Kiểm tra quyền sở hữu & trạng thái vé.
      2. Kiểm tra chênh lệch thời gian: start_time - now >= 2 giờ.
      3. Thu thập tên các ghế và xóa các bản ghi BookingSeat (trả ghế).
      4. Cập nhật booking.status sang 'DA_HUY', held_until = None, updated_at = now.
      5. Cập nhật Payment sang 'refunded' (nếu đã paid) hoặc 'cancelled'.
      6. Commit và trả về kết quả.
    """
    now = datetime.utcnow()
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy đơn vé với ID #{booking_id}"
        )

    # 1. Kiểm tra quyền sở hữu vé
    if booking.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thao tác trên đơn vé này."
        )

    # 2. Kiểm tra trạng thái vé
    current_status = (booking.status or "").upper()
    if current_status in ["DA_HUY", "CANCELLED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn vé này đã được hủy trước đó."
        )
    if current_status in ["HET_HAN", "EXPIRED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn giữ chỗ đã hết hạn, không thể thực hiện hủy vé."
        )

    # 3. Kiểm tra điều kiện thời gian: trước giờ chiếu ít nhất 2 tiếng (Task T3C6D1A)
    st = booking.showtime
    if not st or not st.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suất chiếu không hợp lệ hoặc không xác định được thời gian bắt đầu."
        )

    ref_now = _get_effective_ref_now(st.start_time, default_now=now)

    cancellation_deadline = st.start_time - timedelta(hours=2)
    if ref_now > cancellation_deadline:
        diff = st.start_time - ref_now
        if diff.total_seconds() <= 0:
            time_msg = "Suất chiếu đã bắt đầu hoặc đã kết thúc"
        else:
            minutes_left = max(0, int(diff.total_seconds() // 60))
            hours_left = minutes_left // 60
            mins = minutes_left % 60
            time_msg = f"Chỉ còn {hours_left}h{mins:02d}m nữa là đến giờ chiếu"

        deadline_str = cancellation_deadline.strftime("%H:%M ngày %d/%m/%Y")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Chỉ có thể hủy vé trước giờ chiếu ít nhất 2 tiếng ({time_msg}). "
                f"Thời hạn hủy vé cho suất chiếu này đã kết thúc lúc {deadline_str}."
            )
        )

    # 4. Thu thập thông tin các ghế để giải phóng
    released_seats = []
    for bs in booking.booking_seats:
        s_name = bs.seat.seat_number if bs.seat else f"ID {bs.seat_id}"
        released_seats.append(s_name)

    # 5. Xóa BookingSeat để giải phóng UNIQUE constraint ghế trong suất chiếu (trả ghế)
    db.query(BookingSeat).filter(BookingSeat.booking_id == booking.id).delete(synchronize_session=False)

    # 6. Cập nhật trạng thái Booking sang DA_HUY
    booking.status = "DA_HUY"
    booking.held_until = None
    booking.updated_at = now

    # 7. Cập nhật các bản ghi Payment tương ứng
    for p in booking.payments:
        if (p.status or "").lower() in ["success", "paid", "completed"]:
            p.status = "refunded"
        else:
            p.status = "cancelled"

    db.commit()
    db.refresh(booking)

    seat_info = ", ".join(released_seats) if released_seats else "Không có ghế"
    return {
        "success": True,
        "message": f"Đã hủy thành công đơn vé #{booking.booking_code}! Ghế [{seat_info}] đã được giải phóng và trả lại hệ thống.",
        "booking_id": booking.id,
        "booking_code": booking.booking_code,
        "new_status": "DA_HUY",
        "released_seats": released_seats,
        "refund_status": "REFUNDED",
        "cancelled_at": now
    }


def get_booking_detail_for_user(
    db: Session,
    user: User,
    booking_id: Optional[int] = None,
    booking_code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Lấy chi tiết vé điện tử của khách hàng (Task T3C6D1A).
    """
    now = datetime.utcnow()
    query = db.query(Booking)
    if booking_id is not None:
        query = query.filter(Booking.id == booking_id)
    elif booking_code is not None:
        query = query.filter(Booking.booking_code == booking_code)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cần cung cấp booking_id hoặc booking_code."
        )

    booking = query.first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn vé yêu cầu."
        )

    # Kiểm tra quyền: chỉ chủ sở hữu vé hoặc ADMIN mới xem được
    user_role_name = getattr(user.role, "name", "") if hasattr(user, "role") else ""
    if booking.user_id != user.id and user_role_name != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập đơn vé này."
        )

    return format_ticket_response(booking, now)


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


def verify_ticket_by_code(db: Session, booking_code: str) -> Dict[str, Any]:
    """
    Tra cứu thông tin vé điện tử khi quét mã QR (Task T3C72CC).
    Cho phép tra cứu công khai hoặc từ trang soát vé:
    - Hiển thị đầy đủ phim, rạp, phòng, suất chiếu, ghế, người đặt, trạng thái thanh toán.
    - Kiểm tra điều kiện hợp lệ để vào rạp (is_valid_for_entry).
    - Hiển thị trạng thái đã check-in hay chưa.
    """
    now = datetime.utcnow()
    clean_code = (booking_code or "").strip().upper()

    booking = db.query(Booking).filter(func.upper(Booking.booking_code) == clean_code).first()
    if not booking:
        # Hỗ trợ tìm kiếm theo mã vé riêng lẻ dạng TK-{booking_code}-{seat_number} (Rule 9)
        booking = (
            db.query(Booking)
            .join(BookingSeat, Booking.id == BookingSeat.booking_id)
            .join(Seat, BookingSeat.seat_id == Seat.id)
            .filter(
                func.upper(func.concat("TK-", Booking.booking_code, "-", Seat.seat_number)) == clean_code
            )
            .first()
        )
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy vé xem phim với mã '{booking_code}'."
        )

    st = booking.showtime
    movie = st.movie if st else None
    room = st.room if st else None
    cinema = room.cinema if room else None

    # Xác định payment status
    payment_status = "PENDING"
    if booking.status == "DA_THANH_TOAN":
        payment_status = "PAID"
    elif booking.status == "DA_HUY":
        payment_status = "CANCELLED"
    elif booking.status == "HET_HAN":
        payment_status = "EXPIRED"

    # Trạng thái check-in
    is_checked_in = bool(getattr(booking, "is_checked_in", False))
    checked_in_at = getattr(booking, "checked_in_at", None)

    # Điều kiện hợp lệ để vào rạp:
    # 1. Đã thanh toán thành công
    # 2. Chưa từng soát vé (chống dùng lại)
    # 3. Suất chiếu chưa kết thúc quá lâu (nếu có end_time)
    is_valid_for_entry = (
        booking.status == "DA_THANH_TOAN" and
        not is_checked_in and
        (not st or not st.end_time or st.end_time >= now - timedelta(hours=1))
    )

    # Danh sách ghế kèm mã vé riêng cho từng ghế (Rule 9)
    seats_list = []
    for bs in booking.booking_seats:
        s_obj = bs.seat
        tkt_code = getattr(bs, "ticket_code", None) or f"TK-{booking.booking_code}-{s_obj.seat_number if s_obj else bs.seat_id}"
        seats_list.append({
            "seat_id": bs.seat_id,
            "seat_number": s_obj.seat_number if s_obj else f"ID {bs.seat_id}",
            "seat_row": s_obj.seat_row if s_obj else None,
            "seat_column": s_obj.seat_column if s_obj else None,
            "seat_type": s_obj.seat_type if s_obj else "standard",
            "price": bs.price,
            "ticket_code": tkt_code,
        })

    # Mặt nạ số điện thoại khách hàng bảo vệ quyền riêng tư
    customer_phone_masked = None
    customer_name = None
    if booking.user:
        customer_name = booking.user.full_name
        phone = booking.user.phone
        if phone and len(phone) >= 7:
            customer_phone_masked = f"{phone[:3]}****{phone[-3:]}"
        else:
            customer_phone_masked = phone

    return {
        "success": True,
        "booking_id": booking.id,
        "booking_code": booking.booking_code,
        "status": booking.status,
        "payment_status": payment_status,
        "total_price": booking.total_price,
        "created_at": booking.created_at,
        "is_checked_in": is_checked_in,
        "checked_in_at": checked_in_at,
        "is_valid_for_entry": is_valid_for_entry,
        "customer_name": customer_name,
        "customer_phone_masked": customer_phone_masked,
        "movie": {
            "id": movie.id if movie else 0,
            "title": movie.title if movie else "Tên phim",
            "poster_url": movie.poster_url if movie else None,
            "duration_minutes": movie.duration_minutes if movie else 120,
        },
        "showtime": {
            "id": st.id if st else 0,
            "start_time": st.start_time if st else now,
            "end_time": st.end_time if st else now,
            "room_name": room.name if room else "Phòng chiếu",
            "room_type": room.room_type if room else "2D",
        },
        "cinema": {
            "id": cinema.id if cinema else 0,
            "name": cinema.name if cinema else "Rạp chiếu phim",
            "address": cinema.address if cinema else None,
            "city": cinema.city if cinema else None,
        },
        "seats": seats_list,
        "qr_verify_url": f"/pages/ticket-check.html?code={booking.booking_code}"
    }


def checkin_ticket_by_code(db: Session, booking_code: str) -> Dict[str, Any]:
    """
    Xác nhận vé vào rạp / Soát vé khi quét QR (Task T3C72CC).
    Quy tắc nghiệp vụ:
    - Vé phải tồn tại trong CSDL.
    - Vé phải ở trạng thái DA_THANH_TOAN.
    - Chống quét trùng (Duplicate Check-in): Nếu đã check-in rồi -> Báo lỗi kèm thời gian đã soát.
    - Nếu vé DA_HUY hoặc HET_HAN -> Từ chối soát vé.
    - Khi hợp lệ: Cập nhật is_checked_in = True, ghi nhận checked_in_at.
    """
    now = datetime.utcnow()
    clean_code = (booking_code or "").strip().upper()

    booking = db.query(Booking).filter(func.upper(Booking.booking_code) == clean_code).first()
    if not booking:
        # Hỗ trợ checkin qua mã vé riêng lẻ dạng TK-{booking_code}-{seat_number} (Rule 9)
        booking = (
            db.query(Booking)
            .join(BookingSeat, Booking.id == BookingSeat.booking_id)
            .join(Seat, BookingSeat.seat_id == Seat.id)
            .filter(
                func.upper(func.concat("TK-", Booking.booking_code, "-", Seat.seat_number)) == clean_code
            )
            .first()
        )
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy vé với mã '{booking_code}'."
        )

    # 1. Kiểm tra trạng thái đã hủy
    if booking.status == "DA_HUY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VÉ KHÔNG HỢP LỆ: Đơn vé này đã bị hủy trước đó và ghế đã được hoàn trả!"
        )

    # 2. Kiểm tra trạng thái hết hạn
    if booking.status == "HET_HAN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VÉ KHÔNG HỢP LỆ: Đơn vé này đã hết hạn giữ chỗ và chưa được thanh toán!"
        )

    # 3. Kiểm tra trạng thái chưa thanh toán
    if booking.status == "GIU_CHO":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VÉ CHƯA THANH TOÁN: Khách hàng chưa hoàn tất thanh toán cho đơn vé này."
        )

    # 4. Chống quét vé lần 2 (Anti-fraud / Duplicate Check-in)
    if getattr(booking, "is_checked_in", False):
        check_time_str = booking.checked_in_at.strftime("%H:%M:%S ngày %d/%m/%Y") if booking.checked_in_at else "trước đó"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CẢNH BÁO: Vé #{booking.booking_code} ĐÃ ĐƯỢC SOÁT VÀO RẠP lúc {check_time_str}! Không thể tái sử dụng vé."
        )

    # 5. Cập nhật check-in thành công
    booking.is_checked_in = True
    booking.checked_in_at = now
    booking.updated_at = now
    db.commit()
    db.refresh(booking)

    # Thu thập thông tin phòng, rạp, ghế
    st = booking.showtime
    movie = st.movie if st else None
    room = st.room if st else None
    cinema = room.cinema if room else None

    seat_names = []
    for bs in booking.booking_seats:
        s_obj = bs.seat
        seat_names.append(s_obj.seat_number if s_obj else f"ID {bs.seat_id}")

    return {
        "success": True,
        "message": f"Xác nhận vé thành công! Quý khách có thể vào {room.name if room else 'phòng chiếu'}.",
        "booking_code": booking.booking_code,
        "checked_in_at": now,
        "movie_title": movie.title if movie else "Tên phim",
        "room_name": room.name if room else "Phòng chiếu",
        "cinema_name": cinema.name if cinema else "Rạp chiếu phim",
        "seats": seat_names,
        "total_seats": len(seat_names)
    }

