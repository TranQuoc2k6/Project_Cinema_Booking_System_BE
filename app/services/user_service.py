"""
Service layer for User & Customer management (Task: Danh sách khách hàng, tìm kiếm, khoá/mở tài khoản).
Cung cấp các chức năng quản lý khách hàng cho Quản trị viên (Admin):
- Lấy danh sách khách hàng phân trang, lọc theo vai trò (Customer/Admin) và trạng thái (Active/Locked)
- Tìm kiếm linh hoạt theo Họ tên, Email, Số điện thoại
- Thống kê tổng số vé đã đặt và tổng tiền chi tiêu của từng khách hàng
- Xem chi tiết hồ sơ khách hàng và lịch sử đơn vé
- Khóa hoặc Mở khóa tài khoản (ngăn chặn spam / gian lận vé)
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, func

from app.models.user import User
from app.models.role import Role
from app.models.booking import Booking


def format_user_admin(user: User, db: Session) -> Dict[str, Any]:
    """Format đối tượng User sang định dạng JSON trực quan cho giao diện Quản trị viên."""
    role_obj = user.role
    is_admin = (user.role_id == 1) or (role_obj and role_obj.name.upper() == "ADMIN")
    role_name = "ADMIN" if is_admin else "USER"
    role_label = "admin" if is_admin else "customer"

    # Thống kê số lượng vé đã đặt của khách hàng
    total_bookings = db.query(Booking).filter(Booking.user_id == user.id).count()

    # Tổng tiền đã chi tiêu (các đơn vé đã thanh toán thành công)
    spent_query = db.query(func.sum(Booking.total_price)).filter(
        Booking.user_id == user.id,
        Booking.status.in_(["DA_THANH_TOAN", "confirmed", "CONFIRMED", "success"])
    ).scalar()
    total_spent = float(spent_query or 0)

    avatar_url = user.avatar or "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80"
    created_str = user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else ""
    created_date = user.created_at.strftime("%d/%m/%Y") if user.created_at else ""

    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone or "Chưa cập nhật",
        "avatar": avatar_url,
        "role_id": user.role_id,
        "role_name": role_name,
        "role": role_label,
        "is_active": bool(user.is_active),
        "total_bookings": total_bookings,
        "total_spent": total_spent,
        "created_at": created_str,
        "created_date": created_date,
    }


def admin_get_users(
    db: Session,
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    role_filter: Optional[str] = None,
    status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    API lấy danh sách người dùng / khách hàng cho Quản trị viên:
    - Tìm kiếm theo Họ tên, Email, Số điện thoại
    - Lọc theo Vai trò: all, customer (khách hàng), admin (quản trị viên)
    - Lọc theo Trạng thái: all, active (đang hoạt động), blocked (đã bị khóa)
    - Phân trang (page, limit)
    """
    query = db.query(User).outerjoin(Role, User.role_id == Role.id)

    # 1. Tìm kiếm theo từ khóa (Họ tên, Email, SĐT)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.full_name.ilike(term),
                User.email.ilike(term),
                User.phone.like(term)
            )
        )

    # 2. Lọc theo vai trò (Role)
    if role_filter and role_filter.lower() != "all":
        rf = role_filter.lower()
        if rf in ["customer", "user", "khach_hang"]:
            query = query.filter(or_(User.role_id == 2, Role.name.in_(["USER", "CUSTOMER"])))
        elif rf in ["admin", "quan_tri"]:
            query = query.filter(or_(User.role_id == 1, Role.name == "ADMIN"))

    # 3. Lọc theo trạng thái tài khoản (Status)
    if status_filter and status_filter.lower() != "all":
        sf = status_filter.lower()
        if sf in ["active", "hoat_dong", "true", "1"]:
            query = query.filter(User.is_active == True)
        elif sf in ["blocked", "locked", "khoa", "false", "0"]:
            query = query.filter(User.is_active == False)

    total_records = query.count()

    offset_val = (page - 1) * limit
    users = query.order_by(User.id.asc()).offset(offset_val).limit(limit).all()

    items = [format_user_admin(u, db) for u in users]
    total_pages = (total_records + limit - 1) // limit if limit > 0 else 1

    return {
        "status": "success",
        "total": total_records,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "items": items
    }


def admin_get_user_by_id(db: Session, user_id: int) -> Dict[str, Any]:
    """Xem chi tiết thông tin khách hàng và lịch sử đơn vé gần nhất."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài khoản người dùng với ID #{user_id}"
        )

    user_info = format_user_admin(user, db)

    # Lấy tối đa 10 đơn vé gần nhất của khách hàng
    bookings = db.query(Booking).filter(Booking.user_id == user.id).order_by(desc(Booking.created_at)).limit(10).all()
    recent_bookings = []
    for b in bookings:
        st = b.showtime
        movie = st.movie if st else None
        recent_bookings.append({
            "id": b.id,
            "booking_code": b.booking_code,
            "movie_title": movie.title if movie else "Chưa rõ",
            "showtime": st.start_time.strftime("%H:%M • %d/%m/%Y") if st and st.start_time else "",
            "total_price": float(b.total_price or 0),
            "status": b.status,
            "created_at": b.created_at.strftime("%d/%m/%Y %H:%M") if b.created_at else ""
        })

    user_info["recent_bookings"] = recent_bookings

    return {
        "status": "success",
        "data": user_info
    }


def admin_toggle_user_status(
    db: Session,
    user_id: int,
    is_active: bool,
    current_admin_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Khóa hoặc Mở khóa tài khoản:
    - Cập nhật trường is_active
    - Chặn không cho khóa Super Admin (role_id=1)
    - Chặn Admin tự khóa tài khoản của chính mình
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài khoản người dùng với ID #{user_id}."
        )

    # Kiểm tra bảo vệ Admin
    if not is_active:
        if user.role_id == 1 or (user.role and user.role.name.upper() == "ADMIN"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể khóa tài khoản Quản trị viên tối cao (Super Admin)!"
            )
        if current_admin_id and user.id == current_admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bạn không thể tự khóa tài khoản quản trị của chính mình!"
            )

    user.is_active = is_active
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    action_text = "mở khóa" if is_active else "khóa"
    return {
        "status": "success",
        "message": f"Đã {action_text} tài khoản '{user.email}' thành công!",
        "user_id": user.id,
        "is_active": user.is_active
    }
