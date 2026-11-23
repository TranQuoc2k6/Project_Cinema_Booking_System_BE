from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.movie import Movie
from app.models.payment import Payment
from app.models.review import Review
from app.models.showtime import Showtime
from app.models.user import User
from app.schemas.review import (
    ReviewCreate,
    ReviewItemResponse,
    ReviewListResponse,
    ReviewSummaryResponse,
    ReviewUpdate,
)


def get_movie_rating_stats(db: Session, movie_id: int) -> Tuple[float, int, Dict[int, int]]:
    """
    Tính toán điểm đánh giá trung bình, tổng số lượt và phân bổ sao cho một bộ phim.
    Không sử dụng mock data; đọc trực tiếp từ bảng movie_reviews trong MySQL.
    """
    reviews = db.query(Review.rating).filter(Review.movie_id == movie_id).all()
    breakdown = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}

    total_count = len(reviews)
    if total_count == 0:
        return 0.0, 0, breakdown

    total_sum = 0
    for r in reviews:
        score = r[0]
        total_sum += score
        if score in breakdown:
            breakdown[score] += 1

    avg_score = round(total_sum / total_count, 1)
    return avg_score, total_count, breakdown


def get_movie_rating_summary(db: Session, movie_id: int) -> ReviewSummaryResponse:
    """Trả về tóm tắt thống kê điểm đánh giá của một bộ phim."""
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bộ phim yêu cầu.",
        )

    avg_score, total_count, breakdown = get_movie_rating_stats(db, movie_id)
    return ReviewSummaryResponse(
        movie_id=movie_id,
        average_rating=avg_score,
        total_reviews=total_count,
        rating_breakdown=breakdown,
    )


def format_review_item(review: Review, current_user_id: Optional[int] = None) -> ReviewItemResponse:
    """Format đối tượng Review sang schema ReviewItemResponse."""
    user = review.user
    display_name = user.full_name if user and user.full_name else "Khán giả"
    avatar = user.avatar if user else None
    is_owner = bool(current_user_id and review.user_id == current_user_id)

    return ReviewItemResponse(
        id=review.id,
        movie_id=review.movie_id,
        user_id=review.user_id,
        user_name=display_name,
        user_avatar=avatar,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
        updated_at=review.updated_at,
        is_owner=is_owner,
    )


def get_movie_reviews(
    db: Session,
    movie_id: int,
    page: int = 1,
    limit: int = 10,
    current_user_id: Optional[int] = None,
) -> ReviewListResponse:
    """Lấy danh sách đánh giá của bộ phim theo phân trang."""
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bộ phim yêu cầu.",
        )

    avg_score, total_count, breakdown = get_movie_rating_stats(db, movie_id)

    query = (
        db.query(Review)
        .filter(Review.movie_id == movie_id)
        .order_by(Review.created_at.desc())
    )

    offset = (page - 1) * limit
    reviews = query.offset(offset).limit(limit).all()

    items = [format_review_item(r, current_user_id) for r in reviews]
    total_pages = (total_count + limit - 1) // limit if limit > 0 else 1

    return ReviewListResponse(
        movie_id=movie_id,
        average_rating=avg_score,
        total_reviews=total_count,
        rating_breakdown=breakdown,
        items=items,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


def check_user_review_eligibility(
    db: Session,
    user_id: int,
    movie_id: int,
) -> Dict[str, Any]:
    """
    Xác minh điều kiện khách hàng đã thực sự xem phim:
    1. Phải có đơn đặt vé (Booking) liên kết với movie_id này.
    2. Đơn vé phải có trạng thái DA_THANH_TOAN hoặc CONFIRMED.
    3. Suất chiếu (Showtime) của đơn vé phải ĐÃ KẾT THÚC (end_time <= now).
    4. Giao dịch thanh toán (Payment) phải thành công (SUCCESS).
    5. Kiểm tra xem người dùng đã từng gửi đánh giá cho phim này chưa.
    """
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bộ phim yêu cầu.",
        )

    # Kiểm tra đánh giá hiện có của user
    existing_review = (
        db.query(Review)
        .filter(Review.movie_id == movie_id, Review.user_id == user_id)
        .first()
    )
    has_reviewed = existing_review is not None
    existing_item = format_review_item(existing_review, user_id) if existing_review else None

    # Tìm tất cả booking của user cho phim này
    bookings = (
        db.query(Booking)
        .join(Showtime, Booking.showtime_id == Showtime.id)
        .filter(
            Booking.user_id == user_id,
            Showtime.movie_id == movie_id,
        )
        .all()
    )

    if not bookings:
        return {
            "can_review": False,
            "reason": "Bạn chưa mua vé xem phim này. Chỉ khách hàng đã đặt vé và xem phim tại rạp mới có thể gửi đánh giá.",
            "has_reviewed": has_reviewed,
            "existing_review": existing_item,
        }

    # Lọc đơn vé đã thanh toán
    paid_bookings = [
        b for b in bookings if b.status in ["DA_THANH_TOAN", "CONFIRMED"]
    ]
    if not paid_bookings:
        return {
            "can_review": False,
            "reason": "Đơn đặt vé của bạn chưa được thanh toán thành công. Vui lòng hoàn tất thanh toán để có thể đánh giá.",
            "has_reviewed": has_reviewed,
            "existing_review": existing_item,
        }

    # Kiểm tra suất chiếu đã kết thúc chưa
    now = datetime.now()
    ended_bookings = []
    for b in paid_bookings:
        st = b.showtime
        if st:
            st_end = st.end_time
            if not st_end and st.start_time:
                duration = movie.duration_minutes or 120
                st_end = st.start_time + timedelta(minutes=duration)

            if st_end and st_end <= now:
                ended_bookings.append(b)

    if not ended_bookings:
        return {
            "can_review": False,
            "reason": "Suất chiếu của bạn chưa kết thúc. Vui lòng quay lại đánh giá sau khi đã thưởng thức xong bộ phim tại rạp.",
            "has_reviewed": has_reviewed,
            "existing_review": existing_item,
        }

    # Kiểm tra thanh toán SUCCESS (nếu có bảng Payment)
    verified_bookings = []
    for b in ended_bookings:
        has_success_payment = any(p.status == "SUCCESS" for p in b.payments) if b.payments else True
        if has_success_payment or b.status == "DA_THANH_TOAN":
            verified_bookings.append(b)

    if not verified_bookings:
        return {
            "can_review": False,
            "reason": "Không tìm thấy giao dịch thanh toán thành công hợp lệ cho suất chiếu này.",
            "has_reviewed": has_reviewed,
            "existing_review": existing_item,
        }

    return {
        "can_review": True,
        "reason": "Khách hàng đủ điều kiện đánh giá phim.",
        "has_reviewed": has_reviewed,
        "existing_review": existing_item,
    }


def create_or_update_review(
    db: Session,
    movie_id: int,
    user: User,
    payload: ReviewCreate,
) -> Tuple[Review, bool]:
    """
    Tạo mới hoặc cập nhật đánh giá của khách hàng cho phim:
    - Kiểm tra điều kiện đã xem phim (xác minh ở Backend).
    - Nếu đã có đánh giá: Cập nhật rating và comment hiện tại (chống đánh giá trùng).
    - Nếu chưa có: Tạo bản ghi đánh giá mới.
    Trả về: (review_object, is_created: bool).
    """
    eligibility = check_user_review_eligibility(db, user.id, movie_id)
    if not eligibility["can_review"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=eligibility["reason"],
        )

    existing = (
        db.query(Review)
        .filter(Review.movie_id == movie_id, Review.user_id == user.id)
        .first()
    )

    if existing:
        existing.rating = payload.rating
        existing.comment = payload.comment
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing, False

    new_review = Review(
        movie_id=movie_id,
        user_id=user.id,
        rating=payload.rating,
        comment=payload.comment,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)
    return new_review, True


def delete_review(db: Session, movie_id: int, review_id: int, current_user: User) -> dict:
    """Xóa một đánh giá. Chỉ chủ sở hữu đánh giá hoặc Admin mới có quyền xóa."""
    review = (
        db.query(Review)
        .filter(Review.id == review_id, Review.movie_id == movie_id)
        .first()
    )
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đánh giá cần xóa.",
        )

    user_role = (current_user.role.name if current_user.role else "").upper()
    if review.user_id != current_user.id and user_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xóa đánh giá này.",
        )

    db.delete(review)
    db.commit()
    return {"message": "Đã xóa đánh giá thành công."}
