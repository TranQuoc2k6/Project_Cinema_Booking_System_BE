"""
Pydantic Schemas cho Combo bắp nước & Đồ ăn rạp (Task T3C72E6: [Bonus] Combo bắp nước)
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ComboBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Tên combo bắp nước")
    description: Optional[str] = Field(None, max_length=255, description="Chi tiết thành phần combo")
    price: Decimal = Field(..., ge=0, description="Giá niêm yết combo (VNĐ)")
    image_url: Optional[str] = Field(None, max_length=500, description="Link ảnh minh họa combo")
    is_active: bool = Field(True, description="Trạng thái mở bán")


class ComboCreate(ComboBase):
    pass


class ComboUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    price: Optional[Decimal] = Field(None, ge=0)
    image_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class ComboResponse(ComboBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingComboItemRequest(BaseModel):
    """Payload khách hàng gửi khi chọn mua combo kèm theo đơn vé"""
    combo_id: int = Field(..., gt=0, description="ID combo muốn mua")
    quantity: int = Field(1, ge=1, le=20, description="Số lượng combo (1-20)")


class BookingComboResponse(BaseModel):
    """Thông tin combo đã đặt kèm trong vé"""
    id: int
    combo_id: int
    name: str
    quantity: int
    price: Decimal
    total_price: Decimal
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
