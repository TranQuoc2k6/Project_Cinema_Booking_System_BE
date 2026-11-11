from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.models.cinema import Cinema
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomUpdate, RoomResponse
from database import get_db

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


@router.get("", response_model=List[RoomResponse], summary="Lấy danh sách các phòng chiếu")
def get_rooms(
    cinema_id: Optional[int] = Query(None, description="Lọc theo ID cụm rạp"),
    room_type: Optional[str] = Query(None, description="Lọc theo định dạng: 2D, 3D, IMAX, VIP"),
    db: Session = Depends(get_db),
):
    query = db.query(Room)
    if cinema_id is not None:
        query = query.filter(Room.cinema_id == cinema_id)
    if room_type:
        query = query.filter(Room.room_type.ilike(f"%{room_type}%"))
    return query.order_by(Room.id.asc()).all()


@router.get("/{room_id}", response_model=RoomResponse, summary="Lấy chi tiết thông tin một phòng chiếu")
def get_room_detail(room_id: int, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {room_id} not found",
        )
    return room


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED, summary="Tạo phòng chiếu mới")
def create_room(room_in: RoomCreate, db: Session = Depends(get_db)):
    cinema = db.query(Cinema).filter(Cinema.id == room_in.cinema_id).first()
    if not cinema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cinema with id {room_in.cinema_id} not found",
        )
    room = Room(
        cinema_id=room_in.cinema_id,
        name=room_in.name,
        room_type=room_in.room_type or "2D",
        total_seats=room_in.total_seats or 0,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.put("/{room_id}", response_model=RoomResponse, summary="Cập nhật thông tin phòng chiếu")
def update_room(room_id: int, room_in: RoomUpdate, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {room_id} not found",
        )
    update_data = room_in.model_dump(exclude_unset=True)
    if "cinema_id" in update_data and update_data["cinema_id"] is not None:
        cinema = db.query(Cinema).filter(Cinema.id == update_data["cinema_id"]).first()
        if not cinema:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cinema with id {update_data['cinema_id']} not found",
            )
    for field, val in update_data.items():
        setattr(room, field, val)
    db.commit()
    db.refresh(room)
    return room


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xóa phòng chiếu")
def delete_room(room_id: int, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {room_id} not found",
        )
    db.delete(room)
    db.commit()
    return None
