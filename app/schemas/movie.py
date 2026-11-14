from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import date
from typing import Optional, List
from app.schemas.genre import GenreResponse


class MovieCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None
    duration_minutes: Optional[int] = 120
    release_date: Optional[date] = None
    poster: Optional[str] = None
    poster_url: Optional[str] = None
    trailer: Optional[str] = None
    trailer_url: Optional[str] = None
    age_rating: Optional[str] = "P"
    status: Optional[str] = "NOW_SHOWING"
    genre_ids: List[int] = []

    @field_validator("duration", "duration_minutes", mode="before")
    @classmethod
    def validate_duration_create(cls, v):
        if v is not None:
            try:
                val = int(v)
            except (ValueError, TypeError):
                raise ValueError("Thời lượng phim phải là số nguyên hợp lệ.")
            if val <= 0:
                raise ValueError("Thời lượng phim phải lớn hơn 0 phút.")
            return val
        return v


class MovieUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None
    duration_minutes: Optional[int] = None
    release_date: Optional[date] = None
    poster: Optional[str] = None
    poster_url: Optional[str] = None
    trailer: Optional[str] = None
    trailer_url: Optional[str] = None
    age_rating: Optional[str] = None
    status: Optional[str] = None
    genre_ids: Optional[List[int]] = None

    @field_validator("duration", "duration_minutes", mode="before")
    @classmethod
    def validate_duration_update(cls, v):
        if v is not None:
            try:
                val = int(v)
            except (ValueError, TypeError):
                raise ValueError("Thời lượng phim phải là số nguyên hợp lệ.")
            if val <= 0:
                raise ValueError("Thời lượng phim phải lớn hơn 0 phút.")
            return val
        return v


class MovieItemResponse(BaseModel):
    id: int
    title: str
    slug: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    release_date: Optional[date] = None
    poster_url: Optional[str] = None
    trailer_url: Optional[str] = None
    status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MovieListResponse(BaseModel):
    items: List[MovieItemResponse] = []
    page: int = 1
    limit: int = 10
    total: int = 0
    total_pages: int = 1


class MovieResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    duration: Optional[int] = 120
    release_date: Optional[date] = None
    poster: Optional[str] = None
    trailer: Optional[str] = None
    age_rating: Optional[str] = "P"
    status: Optional[str] = "NOW_SHOWING"
    genres: List[GenreResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# SCHEMAS CHO ADMIN QUẢN TRỊ DANH MỤC PHIM (THÊM / SỬA / NGỪNG CHIẾU)
# ============================================================================

class AdminMovieCreate(BaseModel):
    """
    Schema nhận payload thêm phim mới dành cho Quản trị viên (Admin).
    Bắt buộc: title, duration (hoặc duration_minutes > 0), release_date.
    """
    title: str = Field(..., min_length=1, max_length=255, description="Tên tác phẩm / Tên phim")
    duration_minutes: Optional[int] = Field(None, description="Thời lượng phim tính theo phút (> 0)")
    duration: Optional[int] = Field(None, description="Thời lượng phim alias (> 0)")
    release_date: date = Field(..., description="Ngày khởi chiếu chuẩn YYYY-MM-DD")
    description: Optional[str] = Field(None, description="Tóm tắt nội dung phim")
    poster_url: Optional[str] = Field(None, description="Link ảnh Poster phim")
    poster: Optional[str] = Field(None, description="Link ảnh Poster alias")
    trailer_url: Optional[str] = Field(None, description="Link YouTube trailer")
    trailer: Optional[str] = Field(None, description="Link YouTube trailer alias")
    age_rating: Optional[str] = Field("P", description="Phân loại độ tuổi (P, C13, C16, C18)")
    status: Optional[str] = Field("now_showing", description="Trạng thái ban đầu: now_showing, coming_soon, ended")
    genre_ids: List[int] = Field(default=[], description="Danh sách ID các thể loại gán cho phim")

    @field_validator("title")
    @classmethod
    def validate_title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Tên phim không được để trống hoặc chỉ chứa khoảng trắng.")
        return v.strip()

    @field_validator("duration_minutes", "duration", mode="before")
    @classmethod
    def validate_duration_positive(cls, v):
        if v is not None:
            try:
                val = int(v)
            except (ValueError, TypeError):
                raise ValueError("Thời lượng phim phải là số nguyên hợp lệ.")
            if val <= 0:
                raise ValueError("Thời lượng phim phải lớn hơn 0 phút.")
            return val
        return v

    def resolve_duration(self) -> int:
        dur = self.duration_minutes if self.duration_minutes is not None else self.duration
        if dur is None:
            raise ValueError("Thời lượng phim (duration_minutes) là bắt buộc và phải lớn hơn 0 phút.")
        if dur <= 0:
            raise ValueError("Thời lượng phim phải lớn hơn 0 phút.")
        return dur

    def resolve_poster(self) -> Optional[str]:
        return self.poster_url or self.poster

    def resolve_trailer(self) -> Optional[str]:
        return self.trailer_url or self.trailer


class AdminMovieUpdate(BaseModel):
    """
    Schema nhận payload cập nhật / sửa thông tin phim dành cho Quản trị viên (Admin).
    Tất cả các trường là tùy chọn; nếu truyền thì sẽ validate chặt chẽ.
    """
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    duration_minutes: Optional[int] = None
    duration: Optional[int] = None
    release_date: Optional[date] = None
    description: Optional[str] = None
    poster_url: Optional[str] = None
    poster: Optional[str] = None
    trailer_url: Optional[str] = None
    trailer: Optional[str] = None
    age_rating: Optional[str] = None
    status: Optional[str] = None
    genre_ids: Optional[List[int]] = None

    @field_validator("title")
    @classmethod
    def validate_title_update(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Tên phim không được để trống hoặc chỉ chứa khoảng trắng.")
            return v.strip()
        return v

    @field_validator("duration_minutes", "duration", mode="before")
    @classmethod
    def validate_duration_update(cls, v):
        if v is not None:
            try:
                val = int(v)
            except (ValueError, TypeError):
                raise ValueError("Thời lượng phim phải là số nguyên hợp lệ.")
            if val <= 0:
                raise ValueError("Thời lượng phim phải lớn hơn 0 phút.")
            return val
        return v

    def resolve_duration(self) -> Optional[int]:
        if self.duration_minutes is not None:
            return self.duration_minutes
        return self.duration

    def resolve_poster(self) -> Optional[str]:
        return self.poster_url if self.poster_url is not None else self.poster

    def resolve_trailer(self) -> Optional[str]:
        return self.trailer_url if self.trailer_url is not None else self.trailer


class AdminMovieStatusUpdate(BaseModel):
    """
    Schema cập nhật trạng thái phim dành cho Admin (ngừng chiếu hoặc chuyển đổi trạng thái).
    """
    status: str = Field(..., description="Trạng thái mới: now_showing, coming_soon, ended")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ["now_showing", "coming_soon", "ended"]:
            raise ValueError("Trạng thái không hợp lệ. Chỉ chấp nhận một trong các giá trị: 'now_showing', 'coming_soon', 'ended'")
        return clean


class AdminMovieResponse(BaseModel):
    """
    Schema dữ liệu chi tiết phim trả về cho Admin (bao gồm mảng thể loại genres).
    """
    id: int
    title: str
    slug: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: int
    release_date: date
    poster_url: Optional[str] = None
    trailer_url: Optional[str] = None
    age_rating: Optional[str] = "P"
    status: str
    genres: List[GenreResponse] = []

    model_config = ConfigDict(from_attributes=True)


class AdminMovieListResponse(BaseModel):
    """
    Schema danh sách phim phân trang dành cho Admin Portal.
    """
    items: List[AdminMovieResponse] = []
    page: int = 1
    limit: int = 10
    total: int = 0
    total_pages: int = 1
