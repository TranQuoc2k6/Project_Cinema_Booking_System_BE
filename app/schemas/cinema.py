from pydantic import BaseModel, ConfigDict, Field


class CinemaBase(BaseModel):
    name: str = Field(..., max_length=100)
    address: str = Field(..., max_length=255)
    city: str = Field(..., max_length=50)
    phone: str = Field(..., max_length=20)


class CinemaCreate(CinemaBase):
    pass


class CinemaUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=50)
    phone: str | None = Field(None, max_length=20)


class CinemaResponse(CinemaBase):
    id: int

    model_config = ConfigDict(from_attributes=True)