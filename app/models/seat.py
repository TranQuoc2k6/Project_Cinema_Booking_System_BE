from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = (
        CheckConstraint(
            "seat_type IS NULL OR seat_type IN ('standard', 'vip', 'couple')",
            name="check_seat_type",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    seat_number = Column(String(10), nullable=False)
    seat_row = Column(String(5), nullable=False)
    seat_column = Column(Integer, nullable=False)
    seat_type = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=True)

    room = relationship("Room", back_populates="seats")