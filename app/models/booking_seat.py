"""
Model: BookingSeat — Ghế đã được đặt trong một booking

Ràng buộc UNIQUE (showtime_id, seat_id):
  Đảm bảo mỗi ghế chỉ được đặt một lần trong một suất chiếu,
  ngay cả khi nhiều request đến đồng thời (chống đặt trùng ở tầng DB).

Lưu ý:
  Ràng buộc này áp dụng cho cả booking đang GIU_CHO lẫn DA_THANH_TOAN.
  Khi booking chuyển sang DA_HUY hoặc HET_HAN, cần xóa các BookingSeat
  tương ứng (hoặc dùng soft-delete) để trả ghế về trạng thái trống.
"""
from sqlalchemy import Column, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class BookingSeat(Base):
    __tablename__ = "booking_seats"
    __table_args__ = (
        # Chống đặt trùng ghế trong cùng một suất chiếu ở tầng database
        UniqueConstraint(
            "showtime_id",
            "seat_id",
            name="uq_booking_seats_showtime_seat",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Khoá ngoại
    booking_id  = Column(Integer, ForeignKey("bookings.id",  ondelete="CASCADE"), nullable=False)
    showtime_id = Column(Integer, ForeignKey("showtimes.id", ondelete="CASCADE"), nullable=False)
    seat_id     = Column(Integer, ForeignKey("seats.id",     ondelete="RESTRICT"), nullable=False)

    # Snapshot giá tại thời điểm đặt vé
    # (giá suất chiếu hoặc giá ghế VIP/đôi đã nhân hệ số)
    price = Column(Numeric(10, 2), nullable=False, comment="Snapshot giá ghế tại thời điểm mua vé")

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    booking  = relationship("Booking",  back_populates="booking_seats")
    showtime = relationship("Showtime")
    seat     = relationship("Seat")
