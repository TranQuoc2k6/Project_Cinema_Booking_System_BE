"""
Pydantic schemas cho module Booking & BookingSeat.

Phân cấp:
  BookingCreate          → Tạo booking mới (giữ chỗ)
  BookingResponse        → Trả về thông tin booking (list)
  BookingDetailResponse  → Trả về chi tiết kèm danh sách ghế
  BookingStatusUpdate    → Admin cập nhật trạng thái thủ công

  BookingSeatCreate      → Thêm ghế vào booking
  BookingSeatResponse    → Trả về thông tin ghế trong booking
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.combo import BookingComboItemRequest, BookingComboResponse


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BookingStatus(str, Enum):
    GIU_CHO       = "GIU_CHO"        # Đang giữ chỗ — chờ thanh toán
    DA_THANH_TOAN = "DA_THANH_TOAN"  # Đã thanh toán
    DA_HUY        = "DA_HUY"         # Người dùng hủy
    HET_HAN       = "HET_HAN"        # Hết hạn giữ chỗ


# ---------------------------------------------------------------------------
# BookingSeat schemas
# ---------------------------------------------------------------------------

class BookingSeatCreate(BaseModel):
    """Thêm một ghế vào booking."""
    seat_id: int = Field(..., gt=0, description="ID ghế cần đặt")
    price:   Decimal = Field(..., ge=0, max_digits=10, decimal_places=2,
                             description="Giá ghế tại thời điểm đặt vé")


class BookingSeatResponse(BaseModel):
    """Thông tin một ghế trong booking."""
    id:          int
    booking_id:  int
    showtime_id: int
    seat_id:     int
    price:       Decimal

    # Thông tin ghế lồng vào (nếu eager-load)
    seat_number: Optional[str] = None
    seat_row:    Optional[str] = None
    seat_column: Optional[int] = None
    seat_type:   Optional[str] = None
    ticket_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Booking schemas
# ---------------------------------------------------------------------------

class BookingCreate(BaseModel):
    """
    Tạo booking mới (bước 1: giữ ghế).
    FE gửi lên showtime_id và danh sách seat_id muốn chọn.
    Server tự sinh booking_code, tính total_price, đặt held_until = now + 10 phút.
    """
    showtime_id: int = Field(..., gt=0, description="ID suất chiếu")
    seat_ids:    List[int] = Field(
        ..., min_length=1, max_length=8,
        description="Danh sách ID ghế muốn đặt (tối đa 8 ghế/lần)",
    )
    combos:      Optional[List[BookingComboItemRequest]] = Field(
        default=None,
        description="Danh sách combo bắp nước chọn mua kèm (Task T3C72E6)",
    )


class BookingResponse(BaseModel):
    """Thông tin booking trả về trong danh sách."""
    id:           int
    booking_code: str
    user_id:      int
    showtime_id:  int
    total_price:  Decimal
    status:       BookingStatus
    held_until:   Optional[datetime] = None
    created_at:   datetime
    updated_at:   datetime

    model_config = ConfigDict(from_attributes=True)


class BookingDetailResponse(BookingResponse):
    """Chi tiết booking kèm danh sách ghế và combo bắp nước đã đặt."""
    booking_seats: List[BookingSeatResponse] = []
    booking_combos: List[BookingComboResponse] = []

    model_config = ConfigDict(from_attributes=True)


class BookingStatusUpdate(BaseModel):
    """
    Cập nhật trạng thái booking (dành cho Admin hoặc hệ thống nội bộ).
    Ví dụ: chuyển GIU_CHO → DA_HUY khi admin hủy đơn.
    """
    status: BookingStatus = Field(..., description="Trạng thái mới của booking")


# ---------------------------------------------------------------------------
# Utility response wrappers
# ---------------------------------------------------------------------------

class BookingListResponse(BaseModel):
    """Danh sách booking có phân trang."""
    total:    int
    page:     int
    per_page: int
    items:    List[BookingResponse]


# ---------------------------------------------------------------------------
# Seat-hold schemas (Task T3C6902)
# ---------------------------------------------------------------------------

class BookingHoldRequest(BookingCreate):
    """
    Request payload cho endpoint POST /api/bookings/hold.
    Tương đương BookingCreate (showtime_id, seat_ids tối đa 8 ghế).
    """
    pass


class BookingHoldResponse(BookingDetailResponse):
    """
    Response payload cho endpoint POST /api/bookings/hold.
    Bao gồm thông tin booking, booking_code, held_until và danh sách booking_seats.
    """
    pass


# ---------------------------------------------------------------------------
# My Tickets / My Bookings Schemas (Task T3C5D0B)
# ---------------------------------------------------------------------------

class MovieTicketInfo(BaseModel):
    id: int
    title: str
    poster_url: Optional[str] = None
    duration_minutes: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class CinemaTicketInfo(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ShowtimeTicketInfo(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime
    room_name: str
    room_type: str
    cinema: CinemaTicketInfo
    movie: MovieTicketInfo
    model_config = ConfigDict(from_attributes=True)


class TicketSeatItem(BaseModel):
    id: int
    seat_id: int
    seat_number: str
    seat_row: Optional[str] = None
    seat_column: Optional[int] = None
    seat_type: Optional[str] = None
    price: Decimal
    ticket_code: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class MyTicketResponse(BaseModel):
    id: int
    booking_code: str
    status: str
    payment_status: str                     # PENDING / PAID / CANCELLED / EXPIRED
    total_price: Decimal
    held_until: Optional[datetime] = None
    created_at: datetime
    showtime: ShowtimeTicketInfo
    seats: List[TicketSeatItem]
    can_cancel: bool = False
    cancel_deadline: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    is_checked_in: bool = False
    checked_in_at: Optional[datetime] = None
    combos: List[BookingComboResponse] = []
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Ticket Details & Cancellation Schemas (Task T3C6D1A)
# ---------------------------------------------------------------------------

class UserCancelBookingResponse(BaseModel):
    """
    Response payload sau khi khách hàng hủy vé thành công (Task T3C6D1A).
    Bao gồm thông tin ghế đã giải phóng và thời điểm hủy.
    """
    success: bool = True
    message: str = "Đã hủy vé thành công"
    booking_id: int
    booking_code: str
    new_status: str = "DA_HUY"
    released_seats: List[str] = []
    refund_status: Optional[str] = "REFUNDED"
    cancelled_at: datetime


# ---------------------------------------------------------------------------
# Booking Confirmation & Auto-expire schemas (Task T3C6CE6)
# ---------------------------------------------------------------------------

class BookingConfirmRequest(BaseModel):
    """
    Request payload xác nhận đặt vé từ ghế đang giữ.
    Có thể gửi booking_id hoặc booking_code kèm phương thức thanh toán.
    """
    booking_id: Optional[int] = Field(None, description="ID đơn đặt vé (nếu không truyền qua URL)")
    booking_code: Optional[str] = Field(None, description="Mã đơn vé (BK-...)")
    payment_method: Optional[str] = Field("MOMO", description="Phương thức: VNPAY | MOMO | ZALOPAY | CASH | BANKING")
    transaction_id: Optional[str] = Field(None, description="Mã giao dịch ngân hàng / ví điện tử nếu có")
    combos: Optional[List[BookingComboItemRequest]] = Field(None, description="Danh sách combo bắp nước muốn cập nhật/thêm (Task T3C72E6)")


class BookingConfirmResponse(BaseModel):
    """
    Response payload sau khi xác nhận đặt vé thành công.
    Bao gồm tổng tiền đã được tính lại chuẩn xác ở Server.
    """
    success: bool = True
    message: str = "Xác nhận đặt vé thành công"
    booking: BookingDetailResponse
    recalculated_price: Decimal = Field(..., description="Tổng tiền được tính toán lại tại Server")
    payment_id: Optional[int] = None
    payment_status: str = "SUCCESS"


class CleanExpiredResponse(BaseModel):
    """
    Response payload khi dọn dẹp các đơn giữ chỗ quá hạn 10 phút.
    """
    success: bool = True
    expired_bookings_count: int = Field(..., description="Số đơn giữ chỗ quá hạn đã chuyển sang HET_HAN")
    released_seats_count: int = Field(..., description="Số ghế đã được giải phóng trả về trạng thái trống")
    message: str


# ---------------------------------------------------------------------------
# QR Ticket Verification & Check-in Schemas (Task T3C72CC)
# ---------------------------------------------------------------------------

class TicketVerifySeatInfo(BaseModel):
    seat_id: int
    seat_number: str
    seat_row: Optional[str] = None
    seat_column: Optional[int] = None
    seat_type: Optional[str] = "standard"
    price: Decimal
    ticket_code: Optional[str] = None


class TicketVerifyResponse(BaseModel):
    """Thông tin tra cứu vé điện tử khi quét mã QR"""
    success: bool = True
    booking_id: int
    booking_code: str
    status: str                             # GIU_CHO, DA_THANH_TOAN, DA_HUY, HET_HAN
    payment_status: str                     # PAID, PENDING, CANCELLED, EXPIRED
    total_price: Decimal
    created_at: datetime
    is_checked_in: bool = False
    checked_in_at: Optional[datetime] = None
    is_valid_for_entry: bool = False         # Hợp lệ vào rạp: DA_THANH_TOAN và chưa check-in
    customer_name: Optional[str] = None
    customer_phone_masked: Optional[str] = None
    movie: dict
    showtime: dict
    cinema: dict
    seats: List[TicketVerifySeatInfo]
    qr_verify_url: Optional[str] = None


class TicketCheckInResponse(BaseModel):
    """Kết quả sau khi nhân viên quét QR soát vé vào rạp"""
    success: bool = True
    message: str
    booking_code: str
    checked_in_at: datetime
    movie_title: str
    room_name: str
    cinema_name: str
    seats: List[str]
    total_seats: int


