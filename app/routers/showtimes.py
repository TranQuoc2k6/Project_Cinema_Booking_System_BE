from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.pricing import get_pricing_breakdown, get_pricing_config
from app.models.showtime import Showtime
from app.schemas.showtime import (
    CinemaShowtimesResponse,
    PricingConfigResponse,
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
    "/pricing-config",
    response_model=PricingConfigResponse,
    summary="Chính sách giá vé & phụ thu hiện hành",
    description="Xem thông tin biểu giá: hệ số nhân theo loại ghế (Standard, VIP, Couple), phụ thu cuối tuần và phụ thu khung giờ vàng.",
)
def get_public_pricing_config() -> PricingConfigResponse:
    cfg = get_pricing_config()
    return PricingConfigResponse(
        seat_multipliers={k: float(v) for k, v in cfg["seat_multipliers"].items()},
        seat_type_surcharges={k: float(v) for k, v in cfg["seat_type_surcharges"].items()},
        weekend_surcharge=float(cfg["weekend_surcharge"]),
        peak_hour_surcharge=float(cfg["peak_hour_surcharge"]),
        peak_hour_start=cfg["peak_hour_start"],
        peak_hour_end=cfg["peak_hour_end"],
        weekend_days=cfg["weekend_days"],
        include_friday_evening=cfg["include_friday_evening"],
        friday_evening_start_hour=cfg["friday_evening_start_hour"],
    )


@router.get(
    "",
    response_model=list[CinemaShowtimesResponse],
    summary="Lấy suất chiếu theo phim, rạp và ngày",
    description="Trả về tất cả suất chiếu trong khoảng/ngày được lọc, được nhóm theo rạp.",
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


@router.get(
    "/{showtime_id}/pricing",
    summary="Bảng phân tích chi tiết giá vé của suất chiếu",
    description="Trả về chi tiết giá cơ bản, phụ thu cuối tuần, phụ thu giờ vàng và giá áp dụng cho từng loại ghế (Standard, VIP, Couple) của suất chiếu.",
)
def get_showtime_pricing(
    showtime_id: int,
    db: Session = Depends(get_db),
):
    showtime = db.query(Showtime).filter(Showtime.id == showtime_id).first()
    if not showtime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Showtime {showtime_id} not found",
        )

    base_price = Decimal(str(showtime.price))
    breakdown = get_pricing_breakdown(base_price=base_price, showtime_start=showtime.start_time)
    return {
        "showtime_id": showtime.id,
        "start_time": showtime.start_time.isoformat() if showtime.start_time else None,
        "pricing": breakdown,
    }

