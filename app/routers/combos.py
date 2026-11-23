"""
Router cho khách hàng xem và chọn Combo bắp nước (Task T3C72E6: [Bonus] Combo bắp nước)
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from app.schemas.combo import ComboResponse
from app.services import combo_service

router = APIRouter(prefix="/api/combos", tags=["Combos - Bắp Nước"])


@router.get(
    "",
    response_model=List[ComboResponse],
    summary="Lấy danh sách combo bắp nước đang mở bán",
    description="Trả về danh sách các combo bắp nước và nước ngọt có sẵn để khách chọn khi đặt vé.",
)
def get_active_combos(db: Session = Depends(get_db)):
    return combo_service.get_active_combos(db)


@router.get(
    "/{combo_id}",
    response_model=ComboResponse,
    summary="Lấy chi tiết một combo bắp nước theo ID",
)
def get_combo_detail(combo_id: int, db: Session = Depends(get_db)):
    return combo_service.get_combo_by_id(db, combo_id)
