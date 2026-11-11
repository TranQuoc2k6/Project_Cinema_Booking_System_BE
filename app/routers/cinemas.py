from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.models.cinema import Cinema
from app.models.room import Room
from app.schemas.cinema import (
    CinemaCreate,
    CinemaUpdate,
    CinemaResponse,
    CinemaDetailResponse,
)
from app.schemas.room import RoomResponse
from database import get_db

router = APIRouter(prefix="/api/cinemas", tags=["Cinemas"])


@router.get("", response_model=List[CinemaResponse], summary="Lấy danh sách các rạp chiếu")
def get_cinemas(
    city: Optional[str] = Query(None, description="Lọc theo thành phố (ví dụ: 'Ha Noi', 'TP. Ho Chi Minh')"),
    db: Session = Depends(get_db),
):
    query = db.query(Cinema)
    if city:
        query = query.filter(Cinema.city.ilike(f"%{city}%"))
    return query.order_by(Cinema.id.asc()).all()


@router.get("/{cinema_id}", response_model=CinemaDetailResponse, summary="Lấy chi tiết rạp chiếu và danh sách phòng")
def get_cinema_detail(cinema_id: int, db: Session = Depends(get_db)):
    cinema = db.query(Cinema).filter(Cinema.id == cinema_id).first()
    if not cinema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cinema with id {cinema_id} not found",
        )
    return cinema


@router.get("/{cinema_id}/rooms", response_model=List[RoomResponse], summary="Lấy danh sách các phòng chiếu của rạp")
def get_cinema_rooms(cinema_id: int, db: Session = Depends(get_db)):
    cinema = db.query(Cinema).filter(Cinema.id == cinema_id).first()
    if not cinema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cinema with id {cinema_id} not found",
        )
    return db.query(Room).filter(Room.cinema_id == cinema_id).order_by(Room.id.asc()).all()


@router.post("", response_model=CinemaResponse, status_code=status.HTTP_201_CREATED, summary="Tạo rạp chiếu mới")
def create_cinema(cinema_in: CinemaCreate, db: Session = Depends(get_db)):
    existing = db.query(Cinema).filter(Cinema.name == cinema_in.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cinema '{cinema_in.name}' already exists",
        )
    cinema = Cinema(
        name=cinema_in.name,
        address=cinema_in.address,
        city=cinema_in.city,
        phone=cinema_in.phone,
    )
    db.add(cinema)
    db.commit()
    db.refresh(cinema)
    return cinema


@router.put("/{cinema_id}", response_model=CinemaResponse, summary="Cập nhật thông tin rạp chiếu")
def update_cinema(cinema_id: int, cinema_in: CinemaUpdate, db: Session = Depends(get_db)):
    cinema = db.query(Cinema).filter(Cinema.id == cinema_id).first()
    if not cinema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cinema with id {cinema_id} not found",
        )
    update_data = cinema_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(cinema, field, val)
    db.commit()
    db.refresh(cinema)
    return cinema


@router.delete("/{cinema_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xóa rạp chiếu")
def delete_cinema(cinema_id: int, db: Session = Depends(get_db)):
    cinema = db.query(Cinema).filter(Cinema.id == cinema_id).first()
    if not cinema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cinema with id {cinema_id} not found",
        )
    db.delete(cinema)
    db.commit()
    return None
