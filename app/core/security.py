import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from app.core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


def get_password_hash(password: str) -> str:
    """
    Tạo hash mật khẩu bảo mật chuẩn SHA-256 kèm salt.
    Định dạng lưu trữ: sha256$salt$hash
    """
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return f"sha256${salt}${key}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Xác thực mật khẩu người dùng nhập vào so với chuỗi hash trong CSDL.
    """
    try:
        if not hashed_password or "$" not in hashed_password:
            return False
        algorithm, salt, stored_hash = hashed_password.split("$")
        if algorithm != "sha256":
            return False
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        return computed_hash == stored_hash
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Tạo JWT access token chứa thông tin xác thực và quyền người dùng.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Giải mã và kiểm tra tính hợp lệ của JWT token.
    Trả về payload nếu token hợp lệ, None nếu hết hạn hoặc không đúng chữ ký.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
