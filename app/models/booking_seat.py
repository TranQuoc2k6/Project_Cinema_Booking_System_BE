from sqlalchemy import Column, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class BookingSeat(Base):
    __tablename__ = "booking_seats"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    seat_id = Column(Integer, ForeignKey("seats.id"), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)  # Snapshot giá ghế tại thời điểm mua vé

    # Quan hệ N-1 với Booking và Seat
    booking = relationship("Booking", back_populates="booking_seats")
    seat = relationship("Seat")
