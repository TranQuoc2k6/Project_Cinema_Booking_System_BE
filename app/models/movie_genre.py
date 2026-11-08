from sqlalchemy import Table, Column, Integer, ForeignKey
from database import Base


movie_genres = Table(
    "movie_genres",
    Base.metadata,

    Column(
        "movie_id",
        Integer,
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True
    ),

    Column(
        "genre_id",
        Integer,
        ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True
    )
)