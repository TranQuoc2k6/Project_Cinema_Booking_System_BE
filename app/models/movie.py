from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Date, DateTime
from sqlalchemy.orm import relationship
from database import Base
from app.models.genre import movie_genres


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)  # Thời lượng tính theo phút
    release_date = Column(Date, nullable=False)        # Ngày khởi chiếu
    poster_url = Column(String(500), nullable=True)     # Link ảnh poster
    trailer_url = Column(String(500), nullable=True)    # Link trailer YouTube
    status = Column(String(50), default="NOW_SHOWING", nullable=False)  # COMING_SOON | NOW_SHOWING | ENDED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Mối quan hệ N-N với Thể loại
    genres = relationship("Genre", secondary=movie_genres, back_populates="movies")

    # Mối quan hệ 1-N với Suất chiếu
    showtimes = relationship("Showtime", back_populates="movie", cascade="all, delete-orphan")
