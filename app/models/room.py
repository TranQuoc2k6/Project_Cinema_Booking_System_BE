from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cinema_id = Column(Integer, ForeignKey("cinemas.id"), nullable=False)
    name = Column(String(50), nullable=False)
    total_seats = Column(Integer, nullable=False)
    room_type = Column(String(20), nullable=True)

    cinema = relationship("Cinema", back_populates="rooms")
    seats = relationship("Seat", back_populates="room")
    showtimes = relationship("Showtime", back_populates="room")