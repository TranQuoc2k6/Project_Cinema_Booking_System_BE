import os
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from jose import jwt                  # type: ignore[reportMissingModuleSource]
from passlib.context import CryptContext        # type: ignore[reportMissingModuleSource]
import bcrypt                               # type: ignore[reportMissingModuleSource]
from app.core.config import settings

# Khởi tạo đối tượng mã hóa Bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # Chuyển chuỗi mật khẩu sang bytes và giới hạn tối đa 72 bytes
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


# Alias tương thích
get_password_hash = hash_password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Xác thực mật khẩu hỗ trợ cả Bcrypt và SHA-256 (từ seed_data ban đầu).
    """
    if not hashed_password:
        return False

    # Hỗ trợ mật khẩu định dạng sha256$salt$hash từ seed_data
    if hashed_password.startswith("sha256$"):
        try:
            algorithm, salt, stored_hash = hashed_password.split("$")
            computed_hash = hashlib.pbkdf2_hmac(
                'sha256',
                plain_password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            ).hex()
            return computed_hash == stored_hash
        except Exception:
            return False

    # Mặc định kiểm tra qua Bcrypt
    try:
        pwd_bytes = plain_password.encode('utf-8')[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Tạo chuỗi JWT Access Token có thời hạn sử dụng"""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
