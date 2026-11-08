import hashlib
import os

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
