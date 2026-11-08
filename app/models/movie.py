from sqlalchemy import Column, Integer, String, Text, Date
from sqlalchemy.orm import relationship
from database import Base
from app.models.movie_genre import movie_genres


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    duration = Column(Integer, nullable=False)
    release_date = Column(Date, nullable=False)
    poster = Column(String(255), nullable=True)
    trailer = Column(String(255), nullable=True)
    age_rating = Column(String(10), nullable=False)
    status = Column(String(50), nullable=False, default="COMING_SOON")

    genres = relationship(
        "Genre",
        secondary=movie_genres,
        back_populates="movies"
    )