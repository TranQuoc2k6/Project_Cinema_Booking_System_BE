from datetime import date, datetime, time, timedelta
from decimal import Decimal

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
    CinemaShowtimesResponse,
    SeatStatusItem,
    ShowtimeDetailResponse,
    ShowtimeListingItem,
    ShowtimeSeatMapResponse,
)
from app.services.booking_service import clean_expired_holds


# Hệ số nhân giá theo loại ghế
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
    clean_expired_holds(db)

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

    # 4. Xây dựng danh sách ghế kèm trạng thái & giá
    seat_items: list[SeatStatusItem] = []
    for seat in seats:
        seat_type = seat.seat_type or "standard"
        multiplier = SEAT_PRICE_MULTIPLIER.get(seat_type, Decimal("1.0"))
        price = (base_price * multiplier).quantize(Decimal("0.01"))

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
        rows={row: seats_in_row for row, seats_in_row in rows_map.items()},
    )
