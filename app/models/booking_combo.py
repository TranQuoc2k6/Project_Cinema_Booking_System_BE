"""
Model: BookingCombo — Liên kết đơn vé với combo bắp nước đã chọn (Task T3C72E6)
"""
from sqlalchemy import Column, ForeignKey, Integer, Numeric
from sqlalchemy.orm import relationship

from database import Base


class BookingCombo(Base):
    __tablename__ = "booking_combos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    combo_id = Column(Integer, ForeignKey("combos.id", ondelete="RESTRICT"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1, comment="Số lượng combo đặt mua")
    price = Column(Numeric(10, 2), nullable=False, comment="Snapshot đơn giá combo tại thời điểm đặt vé")

    booking = relationship("Booking", back_populates="booking_combos")
    combo = relationship("Combo", back_populates="booking_combos")
