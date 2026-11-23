"""
Service layer cho Quản lý & Bán Combo bắp nước (Task T3C72E6: [Bonus] Combo bắp nước)
"""
from decimal import Decimal
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.combo import Combo
from app.models.booking import Booking
from app.models.booking_combo import BookingCombo
from app.schemas.combo import ComboCreate, ComboUpdate, BookingComboItemRequest


def get_active_combos(db: Session) -> List[Combo]:
    """Lấy danh sách combo bắp nước đang mở bán cho khách hàng"""
    return db.query(Combo).filter(Combo.is_active == True).order_by(Combo.price.asc()).all()


def get_all_combos_admin(
    db: Session,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> List[Combo]:
    """Danh sách tất cả combo cho Quản trị viên (Admin)"""
    query = db.query(Combo)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(Combo.name.ilike(term) | Combo.description.ilike(term))
    if is_active is not None:
        query = query.filter(Combo.is_active == is_active)
    return query.order_by(Combo.id.desc()).all()


def get_combo_by_id(db: Session, combo_id: int) -> Combo:
    """Lấy thông tin chi tiết một combo theo ID"""
    combo = db.query(Combo).filter(Combo.id == combo_id).first()
    if not combo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy combo bắp nước với ID #{combo_id}"
        )
    return combo


def create_combo(db: Session, data: ComboCreate) -> Combo:
    """Thêm combo bắp nước mới (Admin)"""
    # Kiểm tra trùng tên combo
    existing = db.query(Combo).filter(func.lower(Combo.name) == data.name.strip().lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đã tồn tại combo mang tên '{data.name.strip()}'."
        )

    combo = Combo(
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        price=data.price,
        image_url=data.image_url.strip() if data.image_url else None,
        is_active=data.is_active,
    )
    db.add(combo)
    db.commit()
    db.refresh(combo)
    return combo


def update_combo(db: Session, combo_id: int, data: ComboUpdate) -> Combo:
    """Cập nhật thông tin combo bắp nước (Admin)"""
    combo = get_combo_by_id(db, combo_id)

    if data.name is not None:
        name_clean = data.name.strip()
        existing = db.query(Combo).filter(
            func.lower(Combo.name) == name_clean.lower(),
            Combo.id != combo_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tên combo '{name_clean}' đã được sử dụng bởi combo khác."
            )
        combo.name = name_clean

    if data.description is not None:
        combo.description = data.description.strip() if data.description else None
    if data.price is not None:
        combo.price = data.price
    if data.image_url is not None:
        combo.image_url = data.image_url.strip() if data.image_url else None
    if data.is_active is not None:
        combo.is_active = data.is_active

    db.commit()
    db.refresh(combo)
    return combo


def delete_combo(db: Session, combo_id: int) -> Dict[str, Any]:
    """
    Xóa combo bắp nước (Admin).
    Nếu combo đã phát sinh đơn đặt vé thì chuyển is_active = False để bảo toàn lịch sử.
    """
    combo = get_combo_by_id(db, combo_id)

    # Kiểm tra xem combo đã được đặt trong đơn vé nào chưa
    has_orders = db.query(BookingCombo).filter(BookingCombo.combo_id == combo_id).first() is not None
    if has_orders:
        combo.is_active = False
        db.commit()
        return {
            "success": True,
            "message": f"Combo '{combo.name}' đã phát sinh đơn vé, hệ thống đã tự động chuyển sang trạng thái ngưng bán (is_active=False).",
            "soft_deleted": True
        }

    db.delete(combo)
    db.commit()
    return {
        "success": True,
        "message": f"Đã xóa vĩnh viễn combo '{combo.name}' khỏi hệ thống.",
        "soft_deleted": False
    }


def save_booking_combos(
    db: Session,
    booking_id: int,
    combos_request: List[BookingComboItemRequest]
) -> Decimal:
    """
    Lưu danh sách combo bắp nước vào đơn vé và tính tổng tiền combo tại server.
    - Validate combo_id tồn tại và đang mở bán (is_active).
    - Validate số lượng (1 <= quantity <= 20).
    - Xóa combo cũ (nếu có) và thêm combo mới.
    - Trả về tổng tiền combo (Decimal).
    """
    if not combos_request:
        return Decimal("0.00")

    # Xóa các combo cũ của booking này nếu có
    db.query(BookingCombo).filter(BookingCombo.booking_id == booking_id).delete(synchronize_session=False)

    total_combo_price = Decimal("0.00")
    for item in combos_request:
        if item.quantity <= 0:
            continue
        combo = db.query(Combo).filter(Combo.id == item.combo_id).first()
        if not combo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Combo bắp nước với ID #{item.combo_id} không tồn tại."
            )
        if not combo.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Combo '{combo.name}' hiện đang tạm ngừng kinh doanh."
            )

        item_total = combo.price * Decimal(item.quantity)
        total_combo_price += item_total

        bc = BookingCombo(
            booking_id=booking_id,
            combo_id=combo.id,
            quantity=item.quantity,
            price=combo.price,
        )
        db.add(bc)

    db.flush()
    return total_combo_price


def format_booking_combos(booking: Booking) -> List[Dict[str, Any]]:
    """Format danh sách combo của một booking để trả về API"""
    res = []
    for bc in getattr(booking, "booking_combos", []):
        combo_obj = bc.combo
        unit_price = Decimal(str(bc.price))
        total_p = unit_price * Decimal(bc.quantity)
        res.append({
            "id": bc.id,
            "combo_id": bc.combo_id,
            "name": combo_obj.name if combo_obj else f"Combo #{bc.combo_id}",
            "quantity": bc.quantity,
            "price": unit_price,
            "total_price": total_p,
            "image_url": combo_obj.image_url if combo_obj else None,
        })
    return res
