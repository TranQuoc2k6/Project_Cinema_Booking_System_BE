"""
Router quản trị Combo bắp nước dành cho Admin (Task T3C72E6: [Bonus] Combo bắp nước)
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from app.core.dependencies import require_admin
from app.schemas.combo import ComboCreate, ComboUpdate, ComboResponse
from app.services import combo_service

router = APIRouter(prefix="/combos", tags=["Admin - Combos Bắp Nước"])


@router.get(
    "",
    response_model=List[ComboResponse],
    summary="Admin lấy danh sách tất cả combo bắp nước",
)
def admin_get_combos(
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên hoặc mô tả combo"),
    is_active: Optional[bool] = Query(None, description="Lọc theo trạng thái đang bán hay ngưng bán"),
    db: Session = Depends(get_db),
):
    return combo_service.get_all_combos_admin(db, search=search, is_active=is_active)


@router.post(
    "",
    response_model=ComboResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin tạo combo bắp nước mới",
)
def admin_create_combo(
    payload: ComboCreate,
    db: Session = Depends(get_db),
):
    return combo_service.create_combo(db, payload)


@router.get(
    "/{combo_id}",
    response_model=ComboResponse,
    summary="Admin lấy chi tiết một combo",
)
def admin_get_combo(
    combo_id: int,
    db: Session = Depends(get_db),
):
    return combo_service.get_combo_by_id(db, combo_id)


@router.put(
    "/{combo_id}",
    response_model=ComboResponse,
    summary="Admin cập nhật thông tin combo",
)
def admin_update_combo(
    combo_id: int,
    payload: ComboUpdate,
    db: Session = Depends(get_db),
):
    return combo_service.update_combo(db, combo_id, payload)


@router.delete(
    "/{combo_id}",
    summary="Admin xóa hoặc ngừng bán combo",
)
def admin_delete_combo(
    combo_id: int,
    db: Session = Depends(get_db),
):
    return combo_service.delete_combo(db, combo_id)
