from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.room import Room
from app.models.seat import Seat
from app.schemas.seat import (
    SeatMapGenerateRequest,
    SeatMapGenerationResponse,
    SeatResponse,
)
from app.services.seat_service import generate_seat_layout
from database import get_db

router = APIRouter(prefix="/api/rooms", tags=["Seats"])


@router.post(
    "/{room_id}/seats/generate",
    response_model=SeatMapGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_room_seat_map(
    room_id: int,
    layout: SeatMapGenerateRequest,
    db: Session = Depends(get_db),
) -> SeatMapGenerationResponse:
    room = db.query(Room).filter(Room.id == room_id).with_for_update().first()
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found",
        )

    has_seats = db.query(Seat.id).filter(Seat.room_id == room_id).first() is not None
    if has_seats:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room already has seats; existing seat maps are not overwritten",
        )

    generated_seats = generate_seat_layout(
        rows=layout.rows,
        columns=layout.columns,
        vip_rows=layout.vip_rows,
        couple_rows=layout.couple_rows,
    )
    seats = [
        Seat(room_id=room_id, **seat_data)
        for seat_data in generated_seats
    ]
    db.add_all(seats)
    room.total_seats = len(seats)
    db.flush()
    db.commit()

    return SeatMapGenerationResponse(
        room_id=room_id,
        rows=layout.rows,
        columns=layout.columns,
        total_seats=len(seats),
        seats=[SeatResponse.model_validate(seat) for seat in seats],
    )