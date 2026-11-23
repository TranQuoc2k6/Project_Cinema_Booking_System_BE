from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewCreate(BaseModel):
    rating: int = Field(..., description="Số sao đánh giá từ 1 đến 5")
    comment: str = Field(..., description="Nội dung nhận xét/bình luận phim")

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if v is None or not (1 <= v <= 5):
            raise ValueError("Số sao đánh giá phải từ 1 đến 5 sao.")
        return v

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, v: str) -> str:
        if v is None:
            raise ValueError("Nội dung bình luận không được để trống.")
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Nội dung bình luận không được để trống hoặc chỉ chứa khoảng trắng.")
        if len(trimmed) < 2:
            raise ValueError("Nội dung bình luận quá ngắn (tối thiểu 2 ký tự).")
        if len(trimmed) > 1000:
            raise ValueError("Nội dung bình luận không được vượt quá 1000 ký tự.")
        return trimmed


class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, description="Số sao đánh giá từ 1 đến 5")
    comment: Optional[str] = Field(None, description="Nội dung nhận xét/bình luận phim")

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 5):
            raise ValueError("Số sao đánh giá phải từ 1 đến 5 sao.")
        return v

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Nội dung bình luận không được để trống hoặc chỉ chứa khoảng trắng.")
            if len(trimmed) < 2:
                raise ValueError("Nội dung bình luận quá ngắn (tối thiểu 2 ký tự).")
            if len(trimmed) > 1000:
                raise ValueError("Nội dung bình luận không được vượt quá 1000 ký tự.")
            return trimmed
        return v


class ReviewItemResponse(BaseModel):
    id: int
    movie_id: int
    user_id: int
    user_name: str
    user_avatar: Optional[str] = None
    rating: int
    comment: str
    created_at: datetime
    updated_at: datetime
    is_owner: bool = False

    model_config = ConfigDict(from_attributes=True)


class ReviewSummaryResponse(BaseModel):
    movie_id: int
    average_rating: float = 0.0
    total_reviews: int = 0
    rating_breakdown: Dict[int, int] = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}


class ReviewListResponse(BaseModel):
    movie_id: int
    average_rating: float = 0.0
    total_reviews: int = 0
    rating_breakdown: Dict[int, int] = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    items: List[ReviewItemResponse] = []
    page: int = 1
    limit: int = 10
    total_pages: int = 1


class ReviewEligibilityResponse(BaseModel):
    can_review: bool
    reason: str
    has_reviewed: bool = False
    existing_review: Optional[ReviewItemResponse] = None
