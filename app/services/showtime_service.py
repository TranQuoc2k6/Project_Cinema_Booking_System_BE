from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.cinema import Cinema
from app.models.movie import Movie
from app.models.room import Room
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.schemas.showtime import (
    AdminShowtimeCreate,
    AdminShowtimeListResponse,
    AdminShowtimeResponse,
    AdminShowtimeUpdate,
    CinemaShowtimesResponse,
    SeatStatusItem,
    ShowtimeDetailResponse,
    ShowtimeListingItem,
    ShowtimeSeatMapResponse,
)
from app.services.booking_service import clean_expired_holds

from app.core.pricing import (
    calculate_seat_price,
    get_pricing_breakdown,
    get_pricing_config,
    get_showtime_surcharges,
)

# Thời gian dọn phòng sau mỗi suất chiếu (phút)
CLEANING_BUFFER_MINUTES = 15

# Hệ số nhân giá theo loại ghế (tương thích ngược)
SEAT_PRICE_MULTIPLIER: dict[str, Decimal] = {
    "standard": Decimal("1.0"),
    "vip": Decimal("1.5"),
    "couple": Decimal("2.0"),
}


def get_upcoming_showtimes(
    db: Session,
    movie_id: int | None = None,
    cinema_id: int | None = None,
    show_date: date | None = None,
    city: str | None = None,
) -> list[CinemaShowtimesResponse]:
    """Return upcoming showtimes grouped by cinema, with optional filters."""
    now = datetime.now()
    query = (
        db.query(Cinema, Showtime, Movie, Room)
        .join(Room, Showtime.room_id == Room.id)
        .join(Cinema, Room.cinema_id == Cinema.id)
        .join(Movie, Showtime.movie_id == Movie.id)
        .filter(Showtime.start_time >= now)
    )

    if movie_id is not None:
        query = query.filter(Showtime.movie_id == movie_id)
    if cinema_id is not None:
        query = query.filter(Cinema.id == cinema_id)
    if city is not None and city.strip() and city.strip().lower() != "all":
        query = query.filter(Cinema.city.ilike(f"%{city.strip()}%"))
    if show_date is not None:
        day_start = datetime.combine(show_date, time.min)
        day_end = day_start + timedelta(days=1)
        query = query.filter(
            Showtime.start_time >= day_start,
            Showtime.start_time < day_end,
        )

    rows = query.order_by(Cinema.id.asc(), Showtime.start_time.asc()).all()

    # Tự động bổ sung suất chiếu thông minh nếu ngày yêu cầu chưa có suất chiếu nào
    if len(rows) == 0:
        target_check_date = show_date or date.today()
        if target_check_date >= date.today() and (target_check_date - date.today()).days <= 14:
            gen_res = auto_generate_showtimes(db=db, days_ahead=1, start_from_date=target_check_date)
            if gen_res.get("created_count", 0) > 0:
                rows = query.order_by(Cinema.id.asc(), Showtime.start_time.asc()).all()

    grouped: dict[int, CinemaShowtimesResponse] = {}

    for cinema, showtime, movie, room in rows:
        if cinema.id not in grouped:
            grouped[cinema.id] = CinemaShowtimesResponse(
                cinema=cinema,
                showtimes=[],
            )
        movie_genres_list = [g.name for g in movie.genres] if hasattr(movie, "genres") and movie.genres else []
        grouped[cinema.id].showtimes.append(
            ShowtimeListingItem(
                id=showtime.id,
                movie_id=movie.id,
                movie_title=movie.title,
                poster_url=movie.poster_url,
                duration_minutes=movie.duration_minutes,
                genres=movie_genres_list,
                room_id=room.id,
                room_name=room.name,
                room_type=room.room_type,
                start_time=showtime.start_time,
                end_time=showtime.end_time,
                price=showtime.price,
            )
        )

    return list(grouped.values())


def get_showtime_by_id(
    showtime_id: int, db: Session
) -> ShowtimeDetailResponse | None:
    """Lấy thông tin chi tiết một suất chiếu kèm rạp, phòng và ghế trống."""
    row = (
        db.query(Showtime, Movie, Room, Cinema)
        .join(Movie, Showtime.movie_id == Movie.id)
        .join(Room, Showtime.room_id == Room.id)
        .join(Cinema, Room.cinema_id == Cinema.id)
        .filter(Showtime.id == showtime_id)
        .first()
    )
    if not row:
        return None
    showtime, movie, room, cinema = row

    total_seats = db.query(Seat).filter(Seat.room_id == room.id, Seat.is_active == True).count()
    occupied_count = (
        db.query(BookingSeat)
        .join(Booking, BookingSeat.booking_id == Booking.id)
        .filter(
            Booking.showtime_id == showtime_id,
            Booking.status.in_(["PENDING", "CONFIRMED"]),
        )
        .count()
    )
    available_seats = max(0, total_seats - occupied_count)
    movie_genres_list = [g.name for g in movie.genres] if hasattr(movie, "genres") and movie.genres else ["Điện ảnh"]

    return ShowtimeDetailResponse(
        id=showtime.id,
        movie_id=movie.id,
        movie_title=movie.title,
        original_title=getattr(movie, "title", "Phim"),
        poster_url=movie.poster_url or "",
        duration_minutes=movie.duration_minutes or 120,
        age_rating="P",
        genres=movie_genres_list,
        cinema_id=cinema.id,
        cinema_name=cinema.name,
        city=cinema.city,
        cinema_address=cinema.address,
        room_id=room.id,
        room_name=room.name,
        room_type=room.room_type,
        format=room.room_type or "2D",
        start_time=showtime.start_time,
        end_time=showtime.end_time,
        price=showtime.price,
        available_seats=available_seats,
        total_seats=total_seats,
    )


def get_showtime_seat_map(
    showtime_id: int, db: Session
) -> ShowtimeSeatMapResponse:
    """
    Lấy sơ đồ ghế kèm trạng thái (available / held / booked) và giá
    cho một suất chiếu cụ thể.

    Quy tắc trạng thái:
      - booked  : booking.status in ('CONFIRMED', 'DA_THANH_TOAN')
      - held    : booking.status in ('PENDING', 'GIU_CHO')
      - available: không có booking nào hoặc booking đã CANCELLED / HET_HAN
    """
    # 0. Tự động giải phóng các ghế giữ chỗ quá hạn 10 phút trước khi tính toán
    try:
        clean_expired_holds(db)
    except Exception:
        pass

    # 1. Kiểm tra suất chiếu tồn tại
    showtime: Showtime | None = (
        db.query(Showtime).filter(Showtime.id == showtime_id).first()
    )
    if showtime is None:
        return None  # Caller sẽ raise 404

    try:
        base_price: Decimal = Decimal(str(showtime.price))
    except Exception:
        base_price = Decimal("95000.00")

    # Xác định thời gian suất chiếu để tính phụ thu cuối tuần & giờ vàng
    st_start = showtime.start_time if isinstance(getattr(showtime, "start_time", None), datetime) else None
    surcharges = get_showtime_surcharges(st_start)
    pricing_breakdown = get_pricing_breakdown(base_price, st_start)

    # 2. Lấy tất cả ghế của phòng chiếu, sắp xếp theo hàng → cột
    seats: list[Seat] = (
        db.query(Seat)
        .filter(Seat.room_id == showtime.room_id, Seat.is_active == True)
        .order_by(Seat.seat_row, Seat.seat_column)
        .all()
    )

    # 3. Truy vấn trạng thái ghế cho suất chiếu này
    #    Chỉ quan tâm booking PENDING, GIU_CHO, CONFIRMED, DA_THANH_TOAN
    active_statuses = ("PENDING", "CONFIRMED", "GIU_CHO", "DA_THANH_TOAN")
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
        # Nếu một ghế có nhiều booking (edge case), ưu tiên trạng thái đã thanh toán / confirmed
        existing = occupied.get(seat_id)
        if existing not in ("CONFIRMED", "DA_THANH_TOAN"):
            occupied[seat_id] = booking_status

    # 4. Xây dựng danh sách ghế kèm trạng thái & giá (áp dụng phụ thu & hệ số ghế)
    seat_items: list[SeatStatusItem] = []
    for seat in seats:
        seat_type = seat.seat_type or "standard"
        price = calculate_seat_price(
            base_price=base_price,
            seat_type=seat_type,
            showtime_start=st_start,
        )

        raw_status = occupied.get(seat.id)
        if raw_status in ("CONFIRMED", "DA_THANH_TOAN"):
            status = "booked"
        elif raw_status in ("PENDING", "GIU_CHO"):
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
        is_weekend=surcharges["is_weekend"],
        is_peak_hour=surcharges["is_peak_hour"],
        weekend_surcharge=surcharges["weekend_surcharge"],
        peak_hour_surcharge=surcharges["peak_hour_surcharge"],
        pricing_breakdown=pricing_breakdown,
        rows={row: seats_in_row for row, seats_in_row in rows_map.items()},
    )


# ============================================================================
# ADMIN SHOWTIMES MANAGEMENT & CONFLICT CHECKING (SRS / Task)
# ============================================================================

def check_showtime_conflict(
    db: Session,
    room_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_showtime_id: int | None = None,
) -> Showtime | None:
    """
    Kiểm tra xung đột trùng giờ chiếu trong cùng phòng (Room).
    Quy tắc: Thời lượng phim + 15 phút dọn phòng.
    Khoảng thời gian phòng bị chiếm dụng là [start_time, end_time + 15 phút).
    Hai suất chiếu A và B bị trùng nếu:
        A.start_time < B.end_time + 15 phút  AND  A.end_time + 15 phút > B.start_time
    tức là:
        exist.start_time < candidate.end_time + 15 phút  AND  exist.end_time > candidate.start_time - 15 phút
    """
    cleaning_buffer = timedelta(minutes=CLEANING_BUFFER_MINUTES)
    candidate_end_buffer = end_time + cleaning_buffer
    candidate_start_buffer = start_time - cleaning_buffer

    query = (
        db.query(Showtime)
        .join(Movie, Showtime.movie_id == Movie.id)
        .filter(
            Showtime.room_id == room_id,
            Showtime.start_time < candidate_end_buffer,
            Showtime.end_time > candidate_start_buffer,
        )
    )
    if exclude_showtime_id is not None:
        query = query.filter(Showtime.id != exclude_showtime_id)

    return query.first()


def format_admin_showtime_response(
    showtime: Showtime,
    movie: Movie,
    room: Room,
    cinema: Cinema,
    total_bookings: int = 0,
) -> AdminShowtimeResponse:
    now = datetime.now()
    if showtime.start_time > now:
        st_status = "upcoming"
    elif showtime.end_time < now:
        st_status = "finished"
    else:
        st_status = "ongoing"

    return AdminShowtimeResponse(
        id=showtime.id,
        movie_id=movie.id,
        movie_title=movie.title,
        poster_url=movie.poster_url or "",
        duration_minutes=movie.duration_minutes or 120,
        cinema_id=cinema.id,
        cinema_name=cinema.name,
        city=cinema.city,
        room_id=room.id,
        room_name=room.name,
        room_type=room.room_type or "2D",
        start_time=showtime.start_time,
        end_time=showtime.end_time,
        price=showtime.price,
        status=st_status,
        total_bookings=total_bookings,
    )


def raise_conflict_error(conflict: Showtime, room_name: str | None = None):
    c_movie_title = conflict.movie.title if conflict.movie else f"Phim #{conflict.movie_id}"
    c_start = conflict.start_time.strftime("%H:%M ngày %d/%m/%Y")
    c_end = conflict.end_time.strftime("%H:%M")
    c_clean_end = (conflict.end_time + timedelta(minutes=CLEANING_BUFFER_MINUTES)).strftime("%H:%M")
    room_txt = f" tại phòng '{room_name}'" if room_name else ""
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Trùng lịch chiếu! Phòng chiếu{room_txt} đã có suất chiếu '{c_movie_title}' "
            f"từ {c_start} đến {c_end} (kèm 15 phút dọn phòng đến {c_clean_end}). "
            f"Vui lòng chọn khung giờ khác!"
        ),
    )


def admin_get_showtimes(
    db: Session,
    page: int = 1,
    limit: int = 50,
    movie_id: int | None = None,
    cinema_id: int | None = None,
    room_id: int | None = None,
    date_str: str | None = None,
    search: str | None = None,
    status_filter: str | None = None,
) -> AdminShowtimeListResponse:
    query = (
        db.query(Showtime, Movie, Room, Cinema)
        .join(Movie, Showtime.movie_id == Movie.id)
        .join(Room, Showtime.room_id == Room.id)
        .join(Cinema, Room.cinema_id == Cinema.id)
    )

    if movie_id:
        query = query.filter(Showtime.movie_id == movie_id)
    if room_id:
        query = query.filter(Showtime.room_id == room_id)
    if cinema_id:
        query = query.filter(Room.cinema_id == cinema_id)

    if date_str and date_str.strip() and date_str.strip().lower() != "all":
        try:
            target_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
            day_start = datetime.combine(target_date, time.min)
            day_end = day_start + timedelta(days=1)
            query = query.filter(
                Showtime.start_time >= day_start,
                Showtime.start_time < day_end,
            )
        except ValueError:
            pass

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (Movie.title.ilike(term)) | (Cinema.name.ilike(term)) | (Room.name.ilike(term))
        )

    now = datetime.now()
    if status_filter:
        s = status_filter.strip().lower()
        if s == "upcoming":
            query = query.filter(Showtime.start_time > now)
        elif s == "ongoing":
            query = query.filter(Showtime.start_time <= now, Showtime.end_time >= now)
        elif s == "finished":
            query = query.filter(Showtime.end_time < now)

    total = query.count()
    rows = (
        query.order_by(Showtime.start_time.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = []
    for showtime, movie, room, cinema in rows:
        booking_count = (
            db.query(Booking)
            .filter(
                Booking.showtime_id == showtime.id,
                Booking.status.in_(["DA_THANH_TOAN", "GIU_CHO", "CONFIRMED", "PENDING"]),
            )
            .count()
        )
        items.append(format_admin_showtime_response(showtime, movie, room, cinema, booking_count))

    total_pages = max(1, (total + limit - 1) // limit) if total > 0 else 1
    return AdminShowtimeListResponse(
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        items=items,
    )


def admin_get_showtime_by_id(db: Session, showtime_id: int) -> AdminShowtimeResponse:
    row = (
        db.query(Showtime, Movie, Room, Cinema)
        .join(Movie, Showtime.movie_id == Movie.id)
        .join(Room, Showtime.room_id == Room.id)
        .join(Cinema, Room.cinema_id == Cinema.id)
        .filter(Showtime.id == showtime_id)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy suất chiếu với ID {showtime_id}",
        )
    showtime, movie, room, cinema = row
    booking_count = (
        db.query(Booking)
        .filter(
            Booking.showtime_id == showtime.id,
            Booking.status.in_(["DA_THANH_TOAN", "GIU_CHO", "CONFIRMED", "PENDING"]),
        )
        .count()
    )
    return format_admin_showtime_response(showtime, movie, room, cinema, booking_count)


def admin_create_showtime(db: Session, showtime_in: AdminShowtimeCreate) -> AdminShowtimeResponse:
    # 1. Kiểm tra tồn tại phim
    movie = db.query(Movie).filter(Movie.id == showtime_in.movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tác phẩm phim với ID {showtime_in.movie_id}",
        )

    # 2. Kiểm tra tồn tại phòng chiếu
    room = db.query(Room).filter(Room.id == showtime_in.room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phòng chiếu với ID {showtime_in.room_id}",
        )

    # 3. Tính toán và validate thời lượng kết thúc
    duration = movie.duration_minutes or 120
    min_end_time = showtime_in.start_time + timedelta(minutes=duration)

    if showtime_in.end_time is None:
        end_time = min_end_time
    else:
        if showtime_in.end_time < min_end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Thời gian kết thúc không hợp lệ! Phim '{movie.title}' có thời lượng {duration} phút, "
                    f"do đó suất chiếu kết thúc sớm nhất lúc {min_end_time.strftime('%H:%M %d/%m/%Y')}."
                ),
            )
        end_time = showtime_in.end_time

    # 4. Kiểm tra xung đột chặn trùng giờ (thời lượng phim + 15 phút dọn phòng)
    conflict = check_showtime_conflict(
        db=db,
        room_id=showtime_in.room_id,
        start_time=showtime_in.start_time,
        end_time=end_time,
    )
    if conflict:
        raise_conflict_error(conflict, room.name)

    # 5. Lưu suất chiếu
    price = showtime_in.price if showtime_in.price is not None else Decimal("95000.00")
    if price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá vé cơ bản phải lớn hơn 0 VND.",
        )

    new_showtime = Showtime(
        movie_id=movie.id,
        room_id=room.id,
        start_time=showtime_in.start_time,
        end_time=end_time,
        price=price,
    )
    db.add(new_showtime)
    db.commit()
    db.refresh(new_showtime)

    cinema = db.query(Cinema).filter(Cinema.id == room.cinema_id).first()
    return format_admin_showtime_response(new_showtime, movie, room, cinema, 0)


def admin_update_showtime(
    db: Session,
    showtime_id: int,
    showtime_in: AdminShowtimeUpdate,
) -> AdminShowtimeResponse:
    showtime = db.query(Showtime).filter(Showtime.id == showtime_id).first()
    if not showtime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy suất chiếu với ID {showtime_id}",
        )

    target_movie_id = showtime_in.movie_id if showtime_in.movie_id is not None else showtime.movie_id
    target_room_id = showtime_in.room_id if showtime_in.room_id is not None else showtime.room_id
    target_start_time = showtime_in.start_time if showtime_in.start_time is not None else showtime.start_time

    movie = db.query(Movie).filter(Movie.id == target_movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tác phẩm phim với ID {target_movie_id}",
        )

    room = db.query(Room).filter(Room.id == target_room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phòng chiếu với ID {target_room_id}",
        )

    duration = movie.duration_minutes or 120
    min_end_time = target_start_time + timedelta(minutes=duration)

    if showtime_in.end_time is not None:
        if showtime_in.end_time < min_end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Thời gian kết thúc không hợp lệ! Phim '{movie.title}' có thời lượng {duration} phút, "
                    f"do đó suất chiếu kết thúc sớm nhất lúc {min_end_time.strftime('%H:%M %d/%m/%Y')}."
                ),
            )
        target_end_time = showtime_in.end_time
    elif showtime_in.start_time is not None or showtime_in.movie_id is not None:
        target_end_time = min_end_time
    else:
        target_end_time = showtime.end_time

    # Kiểm tra trùng giờ chiếu trong cùng phòng (loại trừ chính suất chiếu đang sửa)
    conflict = check_showtime_conflict(
        db=db,
        room_id=target_room_id,
        start_time=target_start_time,
        end_time=target_end_time,
        exclude_showtime_id=showtime_id,
    )
    if conflict:
        raise_conflict_error(conflict, room.name)

    showtime.movie_id = target_movie_id
    showtime.room_id = target_room_id
    showtime.start_time = target_start_time
    showtime.end_time = target_end_time

    if showtime_in.price is not None:
        if showtime_in.price <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Giá vé cơ bản phải lớn hơn 0 VND.",
            )
        showtime.price = showtime_in.price

    db.commit()
    db.refresh(showtime)

    booking_count = (
        db.query(Booking)
        .filter(
            Booking.showtime_id == showtime.id,
            Booking.status.in_(["DA_THANH_TOAN", "GIU_CHO", "CONFIRMED", "PENDING"]),
        )
        .count()
    )
    cinema = db.query(Cinema).filter(Cinema.id == room.cinema_id).first()
    return format_admin_showtime_response(showtime, movie, room, cinema, booking_count)


def admin_delete_showtime(db: Session, showtime_id: int, force: bool = False):
    showtime = db.query(Showtime).filter(Showtime.id == showtime_id).first()
    if not showtime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy suất chiếu với ID {showtime_id}",
        )

    # Kiểm tra các đơn vé đã thanh toán
    paid_count = (
        db.query(Booking)
        .filter(
            Booking.showtime_id == showtime_id,
            Booking.status.in_(["DA_THANH_TOAN", "CONFIRMED"]),
        )
        .count()
    )
    if paid_count > 0 and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Không thể hủy/xóa suất chiếu #{showtime_id} vì đã có {paid_count} vé được thanh toán. "
                f"Vui lòng hủy vé hoặc liên hệ hoàn tiền trước khi xóa!"
            ),
        )

    db.delete(showtime)
    db.commit()
    return {
        "status": "success",
        "message": f"Đã hủy và xóa thành công suất chiếu #{showtime_id} khỏi hệ thống.",
    }


# ============================================================================
# TỰ ĐỘNG DỌN DẸP SUẤT CHIẾU CŨ & TỰ ĐỘNG SINH SUẤT CHIẾU CHO CÁC NGÀY TỚI
# ============================================================================

def cleanup_past_showtimes(db: Session, older_than_days: int = 0) -> dict:
    """
    Tự động dọn dẹp các suất chiếu phim cũ đã kết thúc trước hôm nay:
    - Tìm các suất chiếu có start_time trước ngày hôm nay (start_time < today_start).
    - Với các suất chiếu KHÔNG có vé đã thanh toán (chưa có booking CONFIRMED hoặc DA_THANH_TOAN):
      Xóa vĩnh viễn khỏi CSDL để không làm rối dữ liệu và giải phóng lịch phòng.
    - Với các suất chiếu ĐÃ CÓ vé đã thanh toán: Giữ lại để bảo toàn lịch sử vé khách hàng.
    - Trả về số lượng suất chiếu đã được xóa.
    """
    today_start = datetime.combine(date.today() - timedelta(days=older_than_days), time.min)

    past_showtimes = (
        db.query(Showtime)
        .filter(Showtime.start_time < today_start)
        .all()
    )

    deleted_count = 0
    preserved_count = 0

    for st in past_showtimes:
        # Kiểm tra xem có vé đã đặt/thanh toán thành công không
        paid_booking_count = (
            db.query(Booking)
            .filter(
                Booking.showtime_id == st.id,
                Booking.status.in_(["DA_THANH_TOAN", "CONFIRMED"]),
            )
            .count()
        )

        if paid_booking_count == 0:
            db.delete(st)
            deleted_count += 1
        else:
            preserved_count += 1

    if deleted_count > 0:
        db.commit()

    return {
        "status": "success",
        "message": f"Đã dọn dẹp {deleted_count} suất chiếu cũ (giữ lại {preserved_count} suất chiếu có lịch sử thanh toán).",
        "deleted_count": deleted_count,
        "preserved_count": preserved_count,
    }


def auto_generate_showtimes(
    db: Session,
    days_ahead: int = 7,
    start_from_date: date | None = None,
) -> dict:
    """
    Tự động sinh các suất chiếu phim thông minh cho các ngày tiếp theo:
    - Quét từng ngày từ start_from_date (mặc định là hôm nay) đến start_from_date + days_ahead.
    - Lấy danh sách phim đang chiếu (NOW_SHOWING), nếu rỗng thì lấy toàn bộ phim.
    - Lấy toàn bộ phòng chiếu và rạp.
    - Duyệt qua từng phòng, lập lịch các khung giờ chuẩn trong ngày (09:00, 11:45, 14:30, 17:15, 20:00, 22:45).
    - Xoay vòng (round-robin) phim để phân bố đều tác phẩm và khung giờ.
    - Tự động bỏ qua các khung giờ đã có suất chiếu trùng (dựa vào check_showtime_conflict).
    - Tự động bỏ qua các khung giờ trong quá khứ nếu lập lịch cho ngày hôm nay.
    - Tính giá vé cơ bản theo loại phòng (IMAX x1.5, VIP x1.3, 2D chuẩn).
    - Lưu vào CSDL và trả về thống kê.
    """
    today = date.today()
    base_date = start_from_date or today
    now = datetime.now()

    movies = db.query(Movie).filter(Movie.status == "NOW_SHOWING").all()
    if not movies:
        movies = db.query(Movie).all()

    rooms = db.query(Room).all()

    if not movies or not rooms:
        return {
            "status": "warning",
            "message": "Không tìm thấy phim hoặc phòng chiếu nào trong hệ thống để sinh suất chiếu.",
            "created_count": 0,
            "days_checked": 0,
        }

    # Các mốc giờ chiếu chuẩn đa dạng trong ngày
    standard_slots = [
        {"hour": 9, "minute": 0, "base_price": 85000},
        {"hour": 11, "minute": 45, "base_price": 90000},
        {"hour": 14, "minute": 30, "base_price": 95000},
        {"hour": 17, "minute": 15, "base_price": 105000},
        {"hour": 20, "minute": 0, "base_price": 115000},
        {"hour": 22, "minute": 45, "base_price": 90000},
    ]

    total_created = 0
    movie_count = len(movies)

    for day_offset in range(days_ahead):
        current_date = base_date + timedelta(days=day_offset)

        for r_idx, room in enumerate(rooms):
            for slot_idx, slot in enumerate(standard_slots):
                # Chọn phim luân phiên theo phòng, ngày và ca chiếu
                movie = movies[(r_idx + day_offset + slot_idx) % movie_count]
                duration = movie.duration_minutes or 120

                start_dt = datetime(
                    current_date.year,
                    current_date.month,
                    current_date.day,
                    slot["hour"],
                    slot["minute"],
                    0,
                )
                end_dt = start_dt + timedelta(minutes=duration)

                # Nếu là ngày hôm nay và giờ chiếu đã trôi qua, bỏ qua
                if start_dt < now + timedelta(minutes=15):
                    continue

                # Kiểm tra xung đột giờ chiếu trong cùng phòng (thời lượng + 15' dọn phòng)
                conflict = check_showtime_conflict(
                    db=db,
                    room_id=room.id,
                    start_time=start_dt,
                    end_time=end_dt,
                )
                if conflict:
                    continue

                # Tính giá vé cơ bản theo loại phòng
                price = slot["base_price"]
                r_type = (room.room_type or "2D").upper()
                if "IMAX" in r_type:
                    price = int(price * 1.5)
                elif "VIP" in r_type or "GOLD" in r_type:
                    price = int(price * 1.3)

                price_dec = Decimal(str(int(price // 1000 * 1000)))

                new_st = Showtime(
                    movie_id=movie.id,
                    room_id=room.id,
                    start_time=start_dt,
                    end_time=end_dt,
                    price=price_dec,
                )
                db.add(new_st)
                total_created += 1

    if total_created > 0:
        db.commit()

    return {
        "status": "success",
        "message": f"Đã tự động tạo thành công {total_created} suất chiếu mới cho {days_ahead} ngày.",
        "created_count": total_created,
        "days_checked": days_ahead,
        "start_date": base_date.strftime("%Y-%m-%d"),
        "end_date": (base_date + timedelta(days=days_ahead - 1)).strftime("%Y-%m-%d"),
    }


