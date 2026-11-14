from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.booking_seat import BookingSeat
from app.models.room import Room
from app.models.seat import Seat
from app.schemas.seat import (
    SeatBatchUpdateRequest,
    SeatMapGenerateRequest,
    SeatMapGenerationResponse,
    SeatResponse,
    SeatUpdate,
    RoomSeatsSummaryResponse,
)
from app.services.seat_service import generate_seat_layout
from database import get_db

router = APIRouter(prefix="/api/rooms", tags=["Seats"])


@router.get(
    "/{room_id}/seats",
    response_model=RoomSeatsSummaryResponse,
    summary="Lấy sơ đồ và danh sách ghế của phòng chiếu",
)
def get_room_seats(
    room_id: int,
    db: Session = Depends(get_db),
) -> RoomSeatsSummaryResponse:
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {room_id} not found",
        )
    seats = (
        db.query(Seat)
        .filter(Seat.room_id == room_id)
        .order_by(Seat.seat_row.asc(), Seat.seat_column.asc())
        .all()
    )

    unique_rows = sorted(list({s.seat_row for s in seats}))
    max_col = max([s.seat_column for s in seats], default=0)
    std_count = sum(1 for s in seats if (s.seat_type or "standard").lower() == "standard")
    vip_count = sum(1 for s in seats if (s.seat_type or "").lower() == "vip")
    cpl_count = sum(1 for s in seats if (s.seat_type or "").lower() == "couple")

    return RoomSeatsSummaryResponse(
        room_id=room_id,
        total_seats=len(seats),
        rows_count=len(unique_rows),
        columns_count=max_col,
        standard_seats=std_count,
        vip_seats=vip_count,
        couple_seats=cpl_count,
        seats=[SeatResponse.model_validate(s) for s in seats],
    )


@router.post(
    "/{room_id}/seats/generate",
    response_model=SeatMapGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sinh sơ đồ ghế tự động cho phòng chiếu",
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
        if not layout.overwrite:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Room already has seats; existing seat maps are not overwritten",
            )
        # Kiểm tra xem ghế đã có booking chưa
        booked = db.query(BookingSeat.id).join(Seat).filter(Seat.room_id == room_id).first()
        if booked is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể tạo lại sơ đồ ghế: Một số ghế đã có đơn đặt vé",
            )
        db.query(Seat).filter(Seat.room_id == room_id).delete(synchronize_session=False)

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


@router.put(
    "/{room_id}/seats/batch",
    summary="Cập nhật loại ghế hoặc trạng thái hàng loạt ghế trong phòng",
)
def batch_update_seats(
    room_id: int,
    payload: SeatBatchUpdateRequest,
    db: Session = Depends(get_db),
):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {room_id} not found",
        )

    seats = db.query(Seat).filter(Seat.room_id == room_id, Seat.id.in_(payload.seat_ids)).all()
    if not seats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy ghế nào phù hợp",
        )

    for s in seats:
        if payload.seat_type is not None:
            s.seat_type = payload.seat_type.value if hasattr(payload.seat_type, "value") else str(payload.seat_type)
        if payload.is_active is not None:
            s.is_active = payload.is_active

    db.commit()
    return {
        "status": "success",
        "message": f"Đã cập nhật {len(seats)} ghế",
        "updated_count": len(seats),
    }


@router.patch(
    "/{room_id}/seats/{seat_id}",
    response_model=SeatResponse,
    summary="Cập nhật cấu hình một ghế đơn lẻ",
)
def update_single_seat(
    room_id: int,
    seat_id: int,
    payload: SeatUpdate,
    db: Session = Depends(get_db),
):
    seat = db.query(Seat).filter(Seat.id == seat_id, Seat.room_id == room_id).first()
    if not seat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seat with id {seat_id} not found in room {room_id}",
        )
    update_data = payload.model_dump(exclude_unset=True)
    if "seat_type" in update_data and update_data["seat_type"] is not None:
        val = update_data["seat_type"]
        update_data["seat_type"] = val.value if hasattr(val, "value") else str(val)
    for k, v in update_data.items():
        setattr(seat, k, v)
    db.commit()
    db.refresh(seat)
    return seat


@router.delete(
    "/{room_id}/seats",
    status_code=status.HTTP_200_OK,
    summary="Xóa toàn bộ sơ đồ ghế của phòng chiếu",
)
def clear_room_seats(
    room_id: int,
    db: Session = Depends(get_db),
):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {room_id} not found",
        )

    booked = db.query(BookingSeat.id).join(Seat).filter(Seat.room_id == room_id).first()
    if booked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa sơ đồ ghế: Ghế của phòng này đã có đơn đặt vé",
        )
    deleted_count = db.query(Seat).filter(Seat.room_id == room_id).delete(synchronize_session=False)
    room.total_seats = 0
    db.commit()
    return {
        "status": "success",
        "message": f"Đã xóa {deleted_count} ghế của phòng chiếu",
        "deleted_count": deleted_count,
    }