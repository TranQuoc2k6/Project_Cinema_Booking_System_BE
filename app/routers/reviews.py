from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, get_optional_current_user
from app.models.user import User
from app.schemas.review import (
    ReviewCreate,
    ReviewEligibilityResponse,
    ReviewItemResponse,
    ReviewListResponse,
    ReviewSummaryResponse,
    ReviewUpdate,
)
from app.services import review_service

router = APIRouter(
    prefix="/api/movies",
    tags=["Movie Reviews"],
)


@router.get(
    "/{movie_id}/reviews",
    response_model=ReviewListResponse,
    summary="Lấy danh sách đánh giá & thống kê điểm của một bộ phim",
    description="Trả về điểm trung bình, tổng số đánh giá, biểu đồ phân bổ số sao và danh sách bình luận (có phân trang).",
)
def get_movie_reviews(
    movie_id: int,
    page: int = Query(1, ge=1, description="Số trang (bắt đầu từ 1)"),
    limit: int = Query(10, ge=1, le=50, description="Số bình luận trên mỗi trang"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id if current_user else None
    return review_service.get_movie_reviews(
        db=db,
        movie_id=movie_id,
        page=page,
        limit=limit,
        current_user_id=user_id,
    )


@router.get(
    "/{movie_id}/reviews/eligibility",
    response_model=ReviewEligibilityResponse,
    summary="Kiểm tra điều kiện khách hàng đã xem phim để đánh giá",
    description="Xác minh khách hàng đã đặt vé hợp lệ, thanh toán thành công và suất chiếu đã kết thúc.",
)
def check_review_eligibility(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return review_service.check_user_review_eligibility(
        db=db,
        user_id=current_user.id,
        movie_id=movie_id,
    )


@router.post(
    "/{movie_id}/reviews",
    response_model=ReviewItemResponse,
    summary="Gửi đánh giá và bình luận phim mới (hoặc cập nhật nếu đã đánh giá)",
    description=(
        "Chỉ khách hàng đã đặt vé thành công và xem xong phim mới được gửi đánh giá.\n"
        "Nếu khách hàng đã có đánh giá trước đó, hệ thống sẽ tự động cập nhật đánh giá đó để chống spam."
    ),
)
def create_or_update_movie_review(
    movie_id: int,
    payload: ReviewCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review, is_created = review_service.create_or_update_review(
        db=db,
        movie_id=movie_id,
        user=current_user,
        payload=payload,
    )
    if is_created:
        response.status_code = status.HTTP_201_CREATED
    else:
        response.status_code = status.HTTP_200_OK

    return review_service.format_review_item(review, current_user.id)


@router.put(
    "/{movie_id}/reviews",
    response_model=ReviewItemResponse,
    summary="Cập nhật đánh giá và bình luận của khách hàng",
    description="Cho phép khách hàng chỉnh sửa số sao và nội dung bình luận của chính mình.",
)
def update_movie_review(
    movie_id: int,
    payload: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(review_service.Review)
        .filter(
            review_service.Review.movie_id == movie_id,
            review_service.Review.user_id == current_user.id,
        )
        .first()
    )
    if not existing:
        # Nếu chưa có, chuyển sang create
        if payload.rating is None or payload.comment is None:
            raise review_service.HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vui lòng cung cấp đầy đủ số sao và bình luận khi tạo đánh giá.",
            )
        create_payload = ReviewCreate(rating=payload.rating, comment=payload.comment)
        review, _ = review_service.create_or_update_review(
            db=db,
            movie_id=movie_id,
            user=current_user,
            payload=create_payload,
        )
        return review_service.format_review_item(review, current_user.id)

    if payload.rating is not None:
        existing.rating = payload.rating
    if payload.comment is not None:
        existing.comment = payload.comment
    existing.updated_at = review_service.datetime.utcnow()

    db.commit()
    db.refresh(existing)
    return review_service.format_review_item(existing, current_user.id)


@router.get(
    "/{movie_id}/rating-summary",
    response_model=ReviewSummaryResponse,
    summary="Lấy tóm tắt điểm đánh giá và tổng số lượt đánh giá phim",
)
def get_movie_rating_summary(
    movie_id: int,
    db: Session = Depends(get_db),
):
    return review_service.get_movie_rating_summary(db=db, movie_id=movie_id)


@router.delete(
    "/{movie_id}/reviews/{review_id}",
    summary="Xóa một đánh giá phim",
    description="Chỉ chủ sở hữu đánh giá hoặc Quản trị viên (Admin) mới có quyền xóa.",
)
def delete_movie_review(
    movie_id: int,
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return review_service.delete_review(
        db=db,
        movie_id=movie_id,
        review_id=review_id,
        current_user=current_user,
    )
