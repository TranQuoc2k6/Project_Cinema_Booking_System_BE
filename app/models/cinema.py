from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Cinema(Base):
    __tablename__ = "cinemas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    city = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)

    rooms = relationship("Room", back_populates="cinema")