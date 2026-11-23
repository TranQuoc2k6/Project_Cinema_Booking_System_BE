from datetime import datetime
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class Review(Base):
    __tablename__ = "movie_reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_review_rating_range"),
        UniqueConstraint("user_id", "movie_id", name="uq_user_movie_review"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(Integer, nullable=False, comment="Số sao đánh giá từ 1 đến 5")
    comment = Column(Text, nullable=False, comment="Nội dung bình luận/nhận xét của khán giả")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    movie = relationship("Movie", back_populates="reviews")
    user = relationship("User", back_populates="reviews")
