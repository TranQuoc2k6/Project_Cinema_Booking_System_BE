"""
Model: Combo — Combo bắp nước và đồ uống (Task T3C72E6: [Bonus] Combo bắp nước)
"""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String
from sqlalchemy.orm import relationship

from database import Base


class Combo(Base):
    __tablename__ = "combos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="Tên combo bắp nước (vd: Combo Solo, Combo Couple...)")
    description = Column(String(255), nullable=True, comment="Chi tiết thành phần combo (vd: 1 Bắp ngọt lớn + 1 Nước có gas)")
    price = Column(Numeric(10, 2), nullable=False, comment="Đơn giá niêm yết của combo")
    image_url = Column(String(500), nullable=True, comment="Ảnh minh họa bắp nước sắc nét")
    is_active = Column(Boolean, default=True, nullable=False, comment="Trạng thái mở bán (True: Đang bán, False: Tạm ngừng)")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    booking_combos = relationship("BookingCombo", back_populates="combo", cascade="all, delete-orphan")
