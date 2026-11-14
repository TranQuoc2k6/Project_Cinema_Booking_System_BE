from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# Schema trả về thông tin Vai trò
class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


# Schema thông tin cơ bản Người dùng
class UserBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Họ và tên người dùng")
    email: EmailStr = Field(..., description="Email đăng nhập duy nhất")
    phone: Optional[str] = Field(None, pattern=r"^(0|\+84)[0-9]{9}$", description="Số điện thoại Việt Nam")
    avatar: Optional[str] = None


# Schema tạo Người dùng mới (Dùng cho Admin hoặc đăng ký)
class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Mật khẩu tối thiểu 6 ký tự")
    role_id: Optional[int] = 2


# Schema cập nhật thông tin Người dùng (Hồ sơ cá nhân)
class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100, description="Họ và tên mới")
    phone: Optional[str] = Field(None, pattern=r"^(0|\+84)[0-9]{9}$", description="Số điện thoại mới")
    avatar: Optional[str] = Field(None, description="URL ảnh đại diện mới")


# Schema đổi mật khẩu (yêu cầu xác thực mật khẩu cũ)
class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=6, description="Mật khẩu hiện tại")
    new_password: str = Field(..., min_length=6, description="Mật khẩu mới (tối thiểu 6 ký tự)")


# Schema phản hồi thông tin Người dùng (Ẩn password_hash)
class UserResponse(UserBase):
    id: int
    role_id: int
    is_active: bool
    created_at: datetime
    role: Optional[RoleResponse] = None

    class Config:
        from_attributes = True
