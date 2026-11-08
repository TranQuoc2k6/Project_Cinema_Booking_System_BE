from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Seat(Base):
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    seat_number = Column(String(20), nullable=False)  # Ví dụ: A01, B05, VIP-C02
    seat_type = Column(String(50), default="STANDARD", nullable=False)  # STANDARD | VIP | COUPLE

    # Quan hệ N-1 với Room
    room = relationship("Room", back_populates="seats")
