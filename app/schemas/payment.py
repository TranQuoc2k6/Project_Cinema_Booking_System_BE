"""
Pydantic schemas cho module Payment (Task T3C6D00).
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PaymentStatusEnum(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PaymentMethodEnum(str, Enum):
    MOMO = "MOMO"
    VNPAY = "VNPAY"
    VISA = "VISA"
    ZALOPAY = "ZALOPAY"
    CASH = "CASH"


class PaymentMethodInfo(BaseModel):
    code: str
    name: str
    description: str
    icon: Optional[str] = None
    is_active: bool = True


class PaymentSandboxRequest(BaseModel):
    """Payload cho thanh toán mô phỏng (Sandbox)."""
    booking_id: Optional[int] = Field(None, description="ID đơn đặt vé")
    booking_code: Optional[str] = Field(None, description="Mã đơn đặt vé (BK-...)")
    payment_method: str = Field("MOMO", description="Phương thức: MOMO | VNPAY | VISA | ZALOPAY")
    status: PaymentStatusEnum = Field(PaymentStatusEnum.SUCCESS, description="Kết quả mô phỏng: SUCCESS | FAILED")
    failure_reason: Optional[str] = Field(None, description="Lý do thất bại nếu status=FAILED")
    amount: Optional[Decimal] = Field(None, description="Số tiền thanh toán")


class PaymentResponse(BaseModel):
    """Thông tin giao dịch thanh toán trả về cho client."""
    id: int
    booking_id: int
    booking_code: str
    amount: Decimal
    payment_method: str
    status: str
    transaction_id: Optional[str] = None
    payment_time: datetime
    message: str
    booking_status: str

    model_config = ConfigDict(from_attributes=True)
