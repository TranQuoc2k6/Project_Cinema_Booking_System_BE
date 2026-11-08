from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


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