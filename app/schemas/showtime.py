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


class ShowtimeResponse(ShowtimeBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ShowtimeListingItem(BaseModel):
    id: int
    movie_id: int
    movie_title: str
    room_id: int
    room_name: str
    room_type: str
    start_time: datetime
    end_time: datetime
    price: Decimal


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
    # Ghế được nhóm theo hàng (key: tên hàng A, B, C...)
    rows: dict[str, list[SeatStatusItem]]