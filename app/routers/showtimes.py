from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.schemas.showtime import (
    CinemaShowtimesResponse,
    ShowtimeDetailResponse,
    ShowtimeSeatMapResponse,
)
from app.services.showtime_service import (
    get_showtime_by_id,
    get_showtime_seat_map,
    get_upcoming_showtimes,
)
from database import get_db

router = APIRouter(prefix="/api/showtimes", tags=["Showtimes"])


@router.get(
    "",
    response_model=list[CinemaShowtimesResponse],
    summary="Lấy suất chiếu theo phim, rạp và ngày",
    description="Chỉ trả về suất chiếu chưa bắt đầu, được nhóm theo rạp.",
)
def list_showtimes(
    movie_id: int | None = Query(None, ge=1),
    movieId: int | None = Query(None, ge=1),
    cinema_id: int | None = Query(None, ge=1),
    cinemaId: int | None = Query(None, ge=1),
    date: date | None = Query(None),
    show_date: date | None = Query(None, alias="date"),
    city: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[CinemaShowtimesResponse]:
    target_movie_id = movie_id if movie_id is not None else movieId
    target_cinema_id = cinema_id if cinema_id is not None else cinemaId
    target_date = show_date if show_date is not None else date
    return get_upcoming_showtimes(
        db=db,
        movie_id=target_movie_id,
        cinema_id=target_cinema_id,
        show_date=target_date,
        city=city,
    )


@router.get(
    "/{showtime_id}/seats",
    response_model=ShowtimeSeatMapResponse,
    summary="Lấy sơ đồ ghế của suất chiếu",
    description=(
        "Trả về toàn bộ sơ đồ ghế kèm trạng thái "
        "(**available** / **held** / **booked**) và giá tiền theo từng loại ghế.\n\n"
        "- `available` — ghế còn trống\n"
        "- `held`      — ghế đang được giữ (booking PENDING, chờ thanh toán)\n"
        "- `booked`    — ghế đã đặt xong (booking CONFIRMED)\n\n"
        "Giá ghế được tính từ giá cơ bản của suất chiếu:\n"
        "- **standard** × 1.0\n"
        "- **vip**      × 1.5\n"
        "- **couple**   × 2.0"
    ),
)
def get_seat_map(
    showtime_id: int,
    db: Session = Depends(get_db),
) -> ShowtimeSeatMapResponse:
    result = get_showtime_seat_map(showtime_id=showtime_id, db=db)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Showtime {showtime_id} not found",
        )
    return result


@router.get(
    "/{showtime_id}",
    response_model=ShowtimeDetailResponse,
    summary="Lấy chi tiết một suất chiếu",
    description="Trả về thông tin chi tiết của một suất chiếu theo ID kèm thông tin phim và cụm rạp.",
)
def get_showtime_detail(
    showtime_id: int,
    db: Session = Depends(get_db),
) -> ShowtimeDetailResponse:
    result = get_showtime_by_id(showtime_id=showtime_id, db=db)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Showtime {showtime_id} not found",
        )
    return result
