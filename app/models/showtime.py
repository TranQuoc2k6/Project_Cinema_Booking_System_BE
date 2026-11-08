from sqlalchemy import Column, Integer, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Showtime(Base):
    __tablename__ = "showtimes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)  # Giá vé cơ bản

    # Quan hệ N-1 với Movie và Room
    movie = relationship("Movie", back_populates="showtimes")
    room = relationship("Room", back_populates="showtimes")

    # Quan hệ 1-N với Booking
    bookings = relationship("Booking", back_populates="showtime", cascade="all, delete-orphan")
