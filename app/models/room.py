from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cinema_id = Column(Integer, ForeignKey("cinemas.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    room_type = Column(String(50), default="2D", nullable=False)  # 2D | 3D | IMAX | VIP
    total_seats = Column(Integer, default=0, nullable=False)

    # Quan hệ N-1 với Cinema
    cinema = relationship("Cinema", back_populates="rooms")

    # Quan hệ 1-N với Seat
    seats = relationship("Seat", back_populates="room", cascade="all, delete-orphan")

    # Quan hệ 1-N với Showtime
    showtimes = relationship("Showtime", back_populates="room", cascade="all, delete-orphan")
