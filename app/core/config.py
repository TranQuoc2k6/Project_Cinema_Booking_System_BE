import os
from dotenv import load_dotenv

load_dotenv()

# Khóa bí mật tối thiểu 32 ký tự theo chuẩn RFC 7518
SECRET_KEY: str = os.getenv("SECRET_KEY", "cinema_booking_system_super_secret_jwt_key_2026_deepmind_production_key")
ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 giờ
