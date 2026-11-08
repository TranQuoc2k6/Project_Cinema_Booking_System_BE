from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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