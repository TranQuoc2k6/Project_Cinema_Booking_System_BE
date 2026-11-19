from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.cinema import CinemaResponse


class ShowtimeBase(BaseModel):
    movie_id: int = Field(..., gt=0)
    room_id: int = Field(..., gt=0)
    start_time: datetime
    end_time: datetime
    base_price: Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class ShowtimeCreate(ShowtimeBase):
    pass


class ShowtimeUpdate(BaseModel):
    movie_id: int | None = Field(None, gt=0)
    room_id: int | None = Field(None, gt=0)
    start_time: datetime | None = None
    end_time: datetime | None = None
    base_price: Decimal | None = Field(
        None, ge=0, max_digits=10, decimal_places=2
    )

    @model_validator(mode="after")
    def validate_time_range(self):
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be later than start_time")
        return self


# ---------------------------------------------------------------------------
# Admin Showtime Schemas
# ---------------------------------------------------------------------------

class AdminShowtimeCreate(BaseModel):
    movie_id: int = Field(..., gt=0, description="ID của phim")
    room_id: int = Field(..., gt=0, description="ID của phòng chiếu")
    start_time: datetime = Field(..., description="Thời gian bắt đầu chiếu")
    end_time: datetime | None = Field(None, description="Thời gian kết thúc (nếu bỏ trống, hệ thống tự tính theo thời lượng phim)")
    price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2, description="Giá vé cơ bản")
    base_price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2, description="Alias cho giá vé cơ bản")

    @model_validator(mode="after")
    def resolve_price_and_time(self):
        if self.price is None and self.base_price is not None:
            self.price = self.base_price
        elif self.price is None:
            self.price = Decimal("95000.00")
        if self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class AdminShowtimeUpdate(BaseModel):
    movie_id: int | None = Field(None, gt=0)
    room_id: int | None = Field(None, gt=0)
    start_time: datetime | None = None
    end_time: datetime | None = None
    price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    base_price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)

    @model_validator(mode="after")
    def resolve_price_and_time(self):
        if self.price is None and self.base_price is not None:
            self.price = self.base_price
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be later than start_time")
        return self


class AdminShowtimeResponse(BaseModel):
    id: int
    movie_id: int
    movie_title: str
    poster_url: str | None = None
    duration_minutes: int | None = 120
    cinema_id: int
    cinema_name: str
    city: str | None = None
    room_id: int
    room_name: str
    room_type: str
    start_time: datetime
    end_time: datetime
    price: Decimal
    status: str = "upcoming"  # upcoming | ongoing | finished
    total_bookings: int = 0

    model_config = ConfigDict(from_attributes=True)


class AdminShowtimeListResponse(BaseModel):
    total: int
    page: int
    limit: int
    total_pages: int
    items: list[AdminShowtimeResponse]


class ShowtimeResponse(ShowtimeBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ShowtimeListingItem(BaseModel):
    id: int
    movie_id: int
    movie_title: str
    poster_url: str | None = None
    duration_minutes: int | None = 120
    genres: list[str] = []
    room_id: int
    room_name: str
    room_type: str
    start_time: datetime
    end_time: datetime
    price: Decimal


class ShowtimeDetailResponse(BaseModel):
    id: int
    movie_id: int
    movie_title: str
    original_title: str | None = None
    poster_url: str | None = None
    duration_minutes: int | None = 120
    age_rating: str | None = "P"
    genres: list[str] = []
    cinema_id: int
    cinema_name: str
    city: str
    cinema_address: str | None = None
    room_id: int
    room_name: str
    room_type: str
    format: str = "2D"
    start_time: datetime
    end_time: datetime
    price: Decimal
    available_seats: int = 0
    total_seats: int = 0


class CinemaShowtimesResponse(BaseModel):
    cinema: CinemaResponse
    showtimes: list[ShowtimeListingItem]


# ---------------------------------------------------------------------------
# Seat-map response schemas  (dùng cho GET /showtimes/{id}/seats)
# ---------------------------------------------------------------------------

class SeatStatus(str, Enum):
    AVAILABLE = "available"
    HELD = "held"        # PENDING booking
    BOOKED = "booked"    # CONFIRMED booking


class SeatStatusItem(BaseModel):
    """Thông tin một ghế trong sơ đồ suất chiếu."""
    id: int
    seat_number: str
    seat_row: str
    seat_column: int
    seat_type: str                  # standard | vip | couple
    status: SeatStatus
    price: Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)

    model_config = ConfigDict(from_attributes=True)


class ShowtimeSeatMapResponse(BaseModel):
    """Toàn bộ sơ đồ ghế của một suất chiếu."""
    showtime_id: int
    room_id: int
    base_price: Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)
    total_seats: int
    available_seats: int
    # Thông tin phụ thu khung giờ & cuối tuần
    is_weekend: bool = False
    is_peak_hour: bool = False
    weekend_surcharge: Decimal = Decimal("0.00")
    peak_hour_surcharge: Decimal = Decimal("0.00")
    pricing_breakdown: dict | None = None
    # Ghế được nhóm theo hàng (key: tên hàng A, B, C...)
    rows: dict[str, list[SeatStatusItem]]


# ---------------------------------------------------------------------------
# Pricing Configuration Schemas (Cấu hình giá theo loại ghế & khung giờ)
# ---------------------------------------------------------------------------

class PricingConfigUpdate(BaseModel):
    seat_multipliers: dict[str, Decimal] | None = Field(None, description="Hệ số nhân theo loại ghế (standard, vip, couple)")
    seat_type_surcharges: dict[str, Decimal] | None = Field(None, description="Phụ thu cố định theo loại ghế (VND)")
    weekend_surcharge: Decimal | None = Field(None, ge=0, description="Phụ thu ngày cuối tuần (VND)")
    peak_hour_surcharge: Decimal | None = Field(None, ge=0, description="Phụ thu khung giờ vàng (VND)")
    peak_hour_start: str | None = Field(None, description="Giờ bắt đầu khung giờ vàng (HH:MM)")
    peak_hour_end: str | None = Field(None, description="Giờ kết thúc khung giờ vàng (HH:MM)")
    weekend_days: list[int] | None = Field(None, description="Danh sách các ngày cuối tuần (0=Mon, 5=Sat, 6=Sun)")
    include_friday_evening: bool | None = Field(None, description="Bao gồm tối thứ 6 là cuối tuần")
    friday_evening_start_hour: int | None = Field(None, ge=0, le=23, description="Giờ bắt đầu tính cuối tuần cho tối thứ 6")


class PricingConfigResponse(BaseModel):
    seat_multipliers: dict[str, float]
    seat_type_surcharges: dict[str, float]
    weekend_surcharge: float
    peak_hour_surcharge: float
    peak_hour_start: str
    peak_hour_end: str
    weekend_days: list[int]
    include_friday_evening: bool
    friday_evening_start_hour: int
