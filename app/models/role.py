from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False, index=True)  # 'ADMIN', 'USER'
    description = Column(String(255), nullable=True)

    # Mối quan hệ 1-N: Một vai trò có thể thuộc về nhiều người dùng
    users = relationship("User", back_populates="role")