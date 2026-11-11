from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.showtime import ShowtimeSeatMapResponse
from app.services.showtime_service import get_showtime_seat_map
from database import get_db

router = APIRouter(prefix="/api/showtimes", tags=["Showtimes"])


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
