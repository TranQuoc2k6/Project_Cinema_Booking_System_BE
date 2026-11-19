"""
Router cho các thao tác Thanh toán & Cổng thanh toán mô phỏng (Task T3C6D00).
"""
from datetime import datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import (
    PaymentMethodInfo,
    PaymentResponse,
    PaymentSandboxRequest,
    PaymentStatusEnum,
)
from app.services.booking_service import clean_expired_holds

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.get(
    "/methods",
    response_model=List[PaymentMethodInfo],
    summary="Danh sách phương thức thanh toán hỗ trợ",
)
def get_payment_methods():
    """Lấy danh sách các cổng thanh toán hỗ trợ (MoMo, VNPAY, Thẻ Quốc Tế, ZaloPay)."""
    return [
        PaymentMethodInfo(
            code="MOMO",
            name="Ví Điện Tử MoMo",
            description="Quét mã QR MoMo hoặc thanh toán qua ứng dụng MoMo",
            icon="momo.png",
            is_active=True,
        ),
        PaymentMethodInfo(
            code="VNPAY",
            name="Cổng VNPAY-QR",
            description="Thanh toán qua ứng dụng ngân hàng, thẻ ATM nội địa hoặc VNPAY-QR",
            icon="vnpay.png",
            is_active=True,
        ),
        PaymentMethodInfo(
            code="VISA",
            name="Thẻ Quốc Tế (Visa / Mastercard)",
            description="Hỗ trợ thẻ tín dụng/ghi nợ quốc tế Visa, Mastercard, JCB bảo mật 3D-Secure",
            icon="visa.png",
            is_active=True,
        ),
        PaymentMethodInfo(
            code="ZALOPAY",
            name="Ví ZaloPay",
            description="Thanh toán qua ví điện tử ZaloPay",
            icon="zalopay.png",
            is_active=True,
        ),
    ]


@router.post(
    "/sandbox",
    response_model=PaymentResponse,
    summary="Thanh toán mô phỏng (Sandbox) cập nhật trạng thái vé (Task T3C6D00)",
    description=(
        "Mô phỏng cổng thanh toán Sandbox: cho phép chọn kết quả SUCCESS hoặc FAILED.\n"
        "- **SUCCESS**: Cập nhật trạng thái vé sang `DA_THANH_TOAN`, lưu bản ghi Payment `SUCCESS`.\n"
        "- **FAILED**: Ghi nhận Payment `FAILED`, giữ vé ở `GIU_CHO` để khách thử lại hoặc trả lý do lỗi."
    ),
)
def process_sandbox_payment(
    payload: PaymentSandboxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. Dọn dẹp các đơn giữ chỗ quá hạn
    clean_expired_holds(db)

    # 2. Tìm đơn đặt vé
    query = db.query(Booking)
    if payload.booking_id:
        booking = query.filter(Booking.id == payload.booking_id).first()
    elif payload.booking_code:
        booking = query.filter(Booking.booking_code == payload.booking_code.strip()).first()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp booking_id hoặc booking_code để thanh toán.",
        )

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn đặt vé cần thanh toán.",
        )

    # 3. Phân quyền: Chỉ chủ đơn vé hoặc Admin mới được thanh toán
    user_role = (current_user.role.name if current_user.role else "").upper()
    if booking.user_id != current_user.id and user_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thực hiện thanh toán cho đơn vé của người khác.",
        )

    now = datetime.utcnow()
    method_str = (payload.payment_method or "MOMO").upper()
    amount_val = payload.amount if payload.amount is not None else Decimal(str(booking.total_price))
    txn_id = f"SANDBOX-{method_str}-{int(now.timestamp())}"

    # 4. Trường hợp Mô Phỏng THÀNH CÔNG (SUCCESS)
    if payload.status == PaymentStatusEnum.SUCCESS:
        # Kiểm tra vé có bị hết hạn hay hủy không
        if booking.status in ["DA_HUY", "HET_HAN"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Đơn vé đã ở trạng thái {booking.status}, không thể thực hiện thanh toán.",
            )

        # Cập nhật trạng thái vé sang DA_THANH_TOAN
        booking.status = "DA_THANH_TOAN"
        booking.held_until = None
        booking.updated_at = now

        # Lưu bản ghi Payment
        payment = Payment(
            booking_id=booking.id,
            amount=amount_val,
            payment_method=method_str,
            status="SUCCESS",
            transaction_id=txn_id,
            payment_time=now,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        return PaymentResponse(
            id=payment.id,
            booking_id=booking.id,
            booking_code=booking.booking_code,
            amount=amount_val,
            payment_method=method_str,
            status="SUCCESS",
            transaction_id=txn_id,
            payment_time=now,
            message="Thanh toán mô phỏng thành công! Đơn vé đã được xác nhận (DA_THANH_TOAN).",
            booking_status=booking.status,
        )

    # 5. Trường hợp Mô Phỏng THẤT BẠI (FAILED)
    else:
        reason = payload.failure_reason or "Tài khoản không đủ số dư hoặc người dùng hủy giao dịch"

        # Ghi nhận bản ghi thanh toán thất bại
        payment = Payment(
            booking_id=booking.id,
            amount=amount_val,
            payment_method=method_str,
            status="FAILED",
            transaction_id=txn_id,
            payment_time=now,
        )
        db.add(payment)
        booking.updated_at = now
        db.commit()
        db.refresh(payment)

        return PaymentResponse(
            id=payment.id,
            booking_id=booking.id,
            booking_code=booking.booking_code,
            amount=amount_val,
            payment_method=method_str,
            status="FAILED",
            transaction_id=txn_id,
            payment_time=now,
            message=f"Thanh toán mô phỏng thất bại: {reason}. Trạng thái vé được giữ nguyên ({booking.status}) để thử lại.",
            booking_status=booking.status,
        )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Xem chi tiết giao dịch thanh toán",
)
def get_payment_detail(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy giao dịch thanh toán #{payment_id}",
        )

    booking = payment.booking
    booking_code = booking.booking_code if booking else "N/A"
    booking_status = booking.status if booking else "N/A"

    return PaymentResponse(
        id=payment.id,
        booking_id=payment.booking_id,
        booking_code=booking_code,
        amount=payment.amount,
        payment_method=payment.payment_method,
        status=payment.status,
        transaction_id=payment.transaction_id,
        payment_time=payment.payment_time,
        message=f"Thông tin giao dịch {payment.status}",
        booking_status=booking_status,
    )
