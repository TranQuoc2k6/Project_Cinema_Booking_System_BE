from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base


class Cinema(Base):
    __tablename__ = "cinemas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    address = Column(String(300), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    phone = Column(String(20), nullable=True)

    # Mối quan hệ 1-N với Phòng chiếu
    rooms = relationship("Room", back_populates="cinema", cascade="all, delete-orphan")

    @property
    def room_count(self) -> int:
        return len(self.rooms) if self.rooms else 0
