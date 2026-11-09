from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    booking_code = Column(String(50), unique=True, nullable=False, index=True)  # Mã tra cứu vé
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    showtime_id = Column(Integer, ForeignKey("showtimes.id", ondelete="CASCADE"), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING | CONFIRMED | CANCELLED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Quan hệ N-1 với User và Showtime
    user = relationship("User")
    showtime = relationship("Showtime", back_populates="bookings")

    # Quan hệ 1-N với BookingSeat và Payment
    booking_seats = relationship("BookingSeat", back_populates="booking", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="booking", cascade="all, delete-orphan")
