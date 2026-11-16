"""
Router cho các thao tác liên quan đến Booking, bao gồm API giữ ghế (seat‑hold).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.booking import BookingHoldRequest, BookingHoldResponse, MyTicketResponse
from app.services import booking_service

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])

@router.post(
    "/hold",
    response_model=BookingHoldResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Yêu cầu không hợp lệ (số ghế > 8 hoặc seat không tồn tại)"},
        404: {"description": "Showtime không tồn tại"},
        409: {"description": "Một hoặc nhiều ghế đã được giữ hoặc đã đặt"},
    },
)
def hold_seats(
    payload: BookingHoldRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tạo một Booking tạm thời (status=GIU_CHO) và giữ các ghế được yêu cầu.
    Trả về thông tin booking bao gồm `booking_code` và thời gian `held_until`.
    """
    booking = booking_service.hold_seats(
        showtime_id=payload.showtime_id,
        seat_ids=payload.seat_ids,
        user_id=current_user.id,
        db=db,
    )
    return booking


@router.get(
    "/my-tickets",
    response_model=list[MyTicketResponse],
    summary="Lấy danh sách vé đã đặt của tôi (Task T3C5D0B)",
    description="Trả về danh sách vé với thông tin phim, rạp, suất, ghế, mã vé, trạng thái thanh toán. Hỗ trợ lọc theo tab: upcoming (sắp chiếu), watched (đã xem), cancelled (đã hủy/hết hạn).",
)
def get_my_tickets(
    status_filter: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """API lấy danh sách vé của người dùng hiện tại"""
    return booking_service.get_user_bookings(
        user_id=current_user.id,
        status_filter=status_filter,
        db=db,
    )


# Alias tương thích cho FE nếu gọi /my-bookings
@router.get(
    "/my-bookings",
    response_model=list[MyTicketResponse],
    include_in_schema=False,
)
def get_my_bookings_alias(
    status_filter: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return booking_service.get_user_bookings(
        user_id=current_user.id,
        status_filter=status_filter,
        db=db,
    )
