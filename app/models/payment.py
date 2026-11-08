from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    payment_method = Column(String(50), nullable=False)  # VNPAY | MOMO | ZALOPAY | CASH
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING | SUCCESS | FAILED
    transaction_id = Column(String(100), unique=True, nullable=True)  # Mã giao dịch ngân hàng
    payment_time = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Quan hệ N-1 với Booking
    booking = relationship("Booking", back_populates="payments")
