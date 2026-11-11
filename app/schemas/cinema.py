from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.room import RoomResponse


class CinemaBase(BaseModel):
    name: str = Field(..., max_length=100)
    address: str = Field(..., max_length=255)
    city: str = Field(..., max_length=50)
    phone: Optional[str] = Field(None, max_length=20)


class CinemaCreate(CinemaBase):
    pass


class CinemaUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)


class CinemaResponse(CinemaBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CinemaDetailResponse(CinemaResponse):
    rooms: List[RoomResponse] = []

    model_config = ConfigDict(from_attributes=True)
