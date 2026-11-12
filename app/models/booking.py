"""
Model: Booking — Đơn đặt vé

Trạng thái (status):
  GIU_CHO      : Ghế đang được giữ, chờ thanh toán (tối đa 10 phút)
  DA_THANH_TOAN: Đã thanh toán thành công
  DA_HUY       : Người dùng chủ động hủy vé
  HET_HAN      : Hết thời gian giữ chỗ, ghế được trả lại
"""
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from database import Base


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('GIU_CHO', 'DA_THANH_TOAN', 'DA_HUY', 'HET_HAN')",
            name="check_booking_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Mã tra cứu vé — unique, hiển thị cho khách hàng (vd: BK-20241111-XXXX)
    booking_code = Column(String(50), unique=True, nullable=False, index=True)

    # Khoá ngoại
    user_id     = Column(Integer, ForeignKey("users.id",     ondelete="CASCADE"), nullable=False)
    showtime_id = Column(Integer, ForeignKey("showtimes.id", ondelete="CASCADE"), nullable=False)

    # Tài chính
    total_price = Column(Numeric(10, 2), nullable=False)  # Tổng tiền tại thời điểm đặt

    # Trạng thái vòng đời
    status = Column(
        String(20),
        default="GIU_CHO",
        nullable=False,
        index=True,
        comment="GIU_CHO | DA_THANH_TOAN | DA_HUY | HET_HAN",
    )

    # Hạn giữ chỗ — NULL nếu đã thanh toán/hủy/hết hạn
    held_until = Column(
        DateTime,
        nullable=True,
        comment="Thời điểm hết hạn giữ chỗ (NULL sau khi thanh toán hoặc hủy)",
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    user     = relationship("User")
    showtime = relationship("Showtime", back_populates="bookings")

    # BookingSeat bị xóa cùng khi Booking bị xóa
    booking_seats = relationship(
        "BookingSeat",
        back_populates="booking",
        cascade="all, delete-orphan",
    )
    payments = relationship(
        "Payment",
        back_populates="booking",
        cascade="all, delete-orphan",
    )
