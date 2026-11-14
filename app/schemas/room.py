from pydantic import BaseModel, ConfigDict, Field


class RoomBase(BaseModel):
    cinema_id: int = Field(..., gt=0)
    name: str = Field(..., max_length=50)
    total_seats: int = Field(..., gt=0)
    room_type: str | None = Field(None, max_length=20)


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    cinema_id: int | None = Field(None, gt=0)
    name: str | None = Field(None, max_length=50)
    total_seats: int | None = Field(None, gt=0)
    room_type: str | None = Field(None, max_length=20)


class RoomResponse(RoomBase):
    id: int
    cinema_name: str | None = None

    model_config = ConfigDict(from_attributes=True)