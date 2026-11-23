"""
Router cho các thao tác liên quan đến Vé điện tử (Task T3C6D1A).
Cung cấp các API:
  - GET /api/tickets/my-tickets : Lấy danh sách vé của tôi
  - GET /api/tickets/{booking_id} : Lấy chi tiết vé điện tử
  - GET /api/tickets/code/{booking_code} : Lấy chi tiết vé theo mã vé
  - POST /api/tickets/{booking_id}/cancel : Hủy vé trước giờ chiếu 2 tiếng
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.booking import (
    MyTicketResponse,
    TicketCheckInResponse,
    TicketVerifyResponse,
    UserCancelBookingResponse,
)
from app.services import booking_service

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])


@router.get(
    "/my-tickets",
    response_model=list[MyTicketResponse],
    summary="Lấy danh sách vé điện tử của tôi",
)
def get_my_tickets(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return booking_service.get_user_bookings(
        user_id=current_user.id,
        status_filter=status_filter,
        db=db,
    )


@router.get(
    "/code/{booking_code}",
    response_model=MyTicketResponse,
    summary="Chi tiết vé điện tử theo mã vé",
)
def get_ticket_by_code(
    booking_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return booking_service.get_booking_detail_for_user(
        db=db,
        user=current_user,
        booking_code=booking_code,
    )


@router.get(
    "/{booking_id}",
    response_model=MyTicketResponse,
    summary="Chi tiết vé điện tử theo ID",
)
def get_ticket_by_id(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return booking_service.get_booking_detail_for_user(
        db=db,
        user=current_user,
        booking_id=booking_id,
    )


@router.post(
    "/{booking_id}/cancel",
    response_model=UserCancelBookingResponse,
    summary="Khách hàng hủy vé điện tử (trước giờ chiếu 2 tiếng)",
)
def cancel_ticket(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return booking_service.user_cancel_booking(
        db=db,
        user=current_user,
        booking_id=booking_id,
    )


# ---------------------------------------------------------------------------
# QR Ticket Verification & Check-in Endpoints (Task T3C72CC)
# ---------------------------------------------------------------------------

@router.get(
    "/verify/{booking_code}",
    response_model=TicketVerifyResponse,
    summary="Tra cứu & Xác thực vé khi quét mã QR (Task T3C72CC)",
    description="Tra cứu thông tin vé qua mã vé (booking_code) khi người dùng hoặc nhân viên quét mã QR trên vé.",
)
def verify_ticket_qr(
    booking_code: str,
    db: Session = Depends(get_db),
):
    return booking_service.verify_ticket_by_code(
        db=db,
        booking_code=booking_code,
    )


@router.post(
    "/verify/{booking_code}/checkin",
    response_model=TicketCheckInResponse,
    summary="Xác nhận vào rạp / Soát vé khi quét QR (Task T3C72CC)",
    description="Nhân viên soát vé bấm xác nhận cho khách vào rạp sau khi quét mã QR. Chống quét vé trùng lặp.",
)
def checkin_ticket_qr(
    booking_code: str,
    db: Session = Depends(get_db),
):
    return booking_service.checkin_ticket_by_code(
        db=db,
        booking_code=booking_code,
    )

