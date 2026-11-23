"""
Router cho các thao tác liên quan đến Booking, bao gồm API giữ ghế (seat‑hold).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.booking import (
    BookingConfirmRequest,
    BookingConfirmResponse,
    BookingHoldRequest,
    BookingHoldResponse,
    CleanExpiredResponse,
    MyTicketResponse,
    TicketCheckInResponse,
    TicketVerifyResponse,
    UserCancelBookingResponse,
)
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
        combos=getattr(payload, "combos", None),
    )
    return booking


@router.post(
    "/{booking_id}/confirm",
    response_model=BookingConfirmResponse,
    summary="Xác nhận đặt vé từ ghế đang giữ (Task T3C6CE6)",
    description="Xác nhận đặt vé từ ghế đang giữ, tính lại tiền ở server; tự chuyển giữ chỗ quá hạn sang HET_HAN để trả ghế.",
)
def confirm_booking_by_id(
    booking_id: int,
    payload: BookingConfirmRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """API xác nhận đặt vé theo ID đơn vé trong URL"""
    payment_method = payload.payment_method if payload else "MOMO"
    transaction_id = payload.transaction_id if payload else None
    combos = payload.combos if payload else None
    return booking_service.confirm_booking(
        db=db,
        user=current_user,
        booking_id=booking_id,
        payment_method=payment_method,
        transaction_id=transaction_id,
        combos=combos,
    )


@router.post(
    "/confirm",
    response_model=BookingConfirmResponse,
    summary="Xác nhận đặt vé bằng payload (Task T3C6CE6)",
    description="Hỗ trợ xác nhận đặt vé truyền qua body JSON (booking_id hoặc booking_code).",
)
def confirm_booking_by_payload(
    payload: BookingConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """API xác nhận đặt vé qua Body JSON"""
    return booking_service.confirm_booking(
        db=db,
        user=current_user,
        booking_id=payload.booking_id,
        booking_code=payload.booking_code,
        payment_method=payload.payment_method or "MOMO",
        transaction_id=payload.transaction_id,
        combos=payload.combos,
    )


@router.post(
    "/clean-expired",
    response_model=CleanExpiredResponse,
    summary="Tự động hủy giữ chỗ quá hạn để trả ghế (Task T3C6CE6)",
    description="Quét toàn bộ đơn giữ chỗ (GIU_CHO/PENDING) đã quá hạn held_until, chuyển sang HET_HAN và giải phóng ghế trả về trạng thái trống.",
)
def trigger_clean_expired(
    db: Session = Depends(get_db),
):
    """API dọn dẹp và giải phóng các ghế giữ chỗ quá hạn 10 phút"""
    return booking_service.clean_expired_holds(db=db)



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


@router.get(
    "/code/{booking_code}",
    response_model=MyTicketResponse,
    summary="Chi tiết vé điện tử theo mã vé (Task T3C6D1A)",
    description="Lấy chi tiết vé điện tử sau khi đặt hoặc tra cứu (mã vé, phim, rạp, phòng, ghế, giờ, điều kiện hủy).",
)
def get_ticket_by_code(
    booking_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """API lấy chi tiết vé điện tử theo mã booking_code"""
    return booking_service.get_booking_detail_for_user(
        db=db,
        user=current_user,
        booking_code=booking_code,
    )


@router.get(
    "/{booking_id}",
    response_model=MyTicketResponse,
    summary="Chi tiết vé điện tử theo ID (Task T3C6D1A)",
    description="Lấy chi tiết vé điện tử theo ID đơn vé, bao gồm mã vé, phim, rạp, phòng, ghế, giờ và cờ can_cancel.",
)
def get_ticket_by_id(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """API lấy chi tiết vé điện tử theo booking_id"""
    return booking_service.get_booking_detail_for_user(
        db=db,
        user=current_user,
        booking_id=booking_id,
    )


@router.post(
    "/{booking_id}/cancel",
    response_model=UserCancelBookingResponse,
    summary="Khách hàng hủy vé (Task T3C6D1A)",
    description="Khách hàng tự hủy vé của mình trước giờ chiếu ít nhất 2 tiếng. Hệ thống sẽ giải phóng ghế và hoàn trả trạng thái.",
)
def cancel_ticket(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """API khách hàng hủy vé xem phim trước giờ chiếu 2 tiếng"""
    return booking_service.user_cancel_booking(
        db=db,
        user=current_user,
        booking_id=booking_id,
    )


@router.put(
    "/{booking_id}/cancel",
    response_model=UserCancelBookingResponse,
    include_in_schema=False,
)
def cancel_ticket_put_alias(
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
    "/ticket-check/{booking_code}",
    response_model=TicketVerifyResponse,
    summary="Tra cứu vé điện tử khi quét mã QR (Task T3C72CC)",
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
    "/ticket-check/{booking_code}/checkin",
    response_model=TicketCheckInResponse,
    summary="Xác nhận vào rạp / Soát vé khi quét QR (Task T3C72CC)",
)
def checkin_ticket_qr(
    booking_code: str,
    db: Session = Depends(get_db),
):
    return booking_service.checkin_ticket_by_code(
        db=db,
        booking_code=booking_code,
    )

