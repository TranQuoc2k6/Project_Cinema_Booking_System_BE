from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SeatType(str, Enum):
    STANDARD = "standard"
    VIP = "vip"
    COUPLE = "couple"


class SeatBase(BaseModel):
    room_id: int = Field(..., gt=0)
    seat_number: str = Field(..., max_length=10)
    seat_row: str = Field(..., max_length=5)
    seat_column: int = Field(..., gt=0)
    seat_type: SeatType | None = SeatType.STANDARD
    is_active: bool | None = True


class SeatCreate(SeatBase):
    pass


class SeatUpdate(BaseModel):
    room_id: int | None = Field(None, gt=0)
    seat_number: str | None = Field(None, max_length=10)
    seat_row: str | None = Field(None, max_length=5)
    seat_column: int | None = Field(None, gt=0)
    seat_type: SeatType | None = None
    is_active: bool | None = None


class SeatResponse(SeatBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class SeatMapGenerateRequest(BaseModel):
    rows: int = Field(..., ge=1, le=2000)
    columns: int = Field(..., ge=1, le=2000)
    vip_rows: int = Field(0, ge=0, le=2000)
    couple_rows: int = Field(0, ge=0, le=2000)
    overwrite: bool = False

    @model_validator(mode="after")
    def validate_layout(self) -> "SeatMapGenerateRequest":
        if self.vip_rows + self.couple_rows > self.rows:
            raise ValueError("Số hàng VIP và ghế đôi không được vượt quá tổng số hàng")
        if self.rows * self.columns > 2000:
            raise ValueError("Sơ đồ không được vượt quá 2000 ghế")
        return self


class SeatMapGenerationResponse(BaseModel):
    room_id: int
    rows: int
    columns: int
    total_seats: int
    seats: list[SeatResponse]


class SeatBatchUpdateRequest(BaseModel):
    seat_ids: list[int] = Field(..., min_length=1)
    seat_type: SeatType | None = None
    is_active: bool | None = None


class RoomSeatsSummaryResponse(BaseModel):
    room_id: int
    total_seats: int
    rows_count: int
    columns_count: int
    standard_seats: int
    vip_seats: int
    couple_seats: int
    seats: list[SeatResponse]