from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base
from app.models.movie_genre import movie_genres


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)

    movies = relationship(
        "Movie",
        secondary=movie_genres,
        back_populates="genres"
    )