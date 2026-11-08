from sqlalchemy import Column, Date, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    release_date = Column(Date, nullable=True)
    poster_url = Column(String(255), nullable=True)
    trailer_url = Column(String(255), nullable=True)
    rating = Column(String(10), nullable=True)
    status = Column(String(20), nullable=True)

    showtimes = relationship("Showtime", back_populates="movie")