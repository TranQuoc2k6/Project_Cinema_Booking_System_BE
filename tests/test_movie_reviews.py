"""
Kiểm thử toàn diện chức năng Đánh giá & Bình luận phim (Task T3C7300):
1. Khách chưa đăng nhập gửi đánh giá (401)
2. Khách đã đăng nhập nhưng chưa đặt vé (403)
3. Khách có booking nhưng chưa thanh toán (403)
4. Khách đã thanh toán nhưng suất chiếu chưa kết thúc (403)
5. Khách đã xem phim và gửi đánh giá hợp lệ (201)
6. Đánh giá 0 sao hoặc trên 5 sao (422)
7. Bình luận rỗng hoặc chỉ có khoảng trắng (422)
8. Đánh giá trùng -> tự động cập nhật đánh giá (200, không nhân bản)
9. Hai khách hàng đánh giá cùng một phim (lưu 2 đánh giá riêng biệt)
10. Điểm trung bình sau khi có nhiều đánh giá được tính toán chính xác
11. Phim chưa có đánh giá (trả về 0.0 sao, 0 lượt, danh sách rỗng)
12. API tóm tắt điểm và danh sách bình luận (phân trang & breakdown)
"""
import os
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Thêm root vào path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, get_db
from app.models import Cinema, Movie, Room, Showtime, Booking, Payment, User, Role, Review
from app.core.security import create_access_token, get_password_hash
from main import app


@pytest.fixture(scope="module")
def test_setup():
    # Sử dụng SQLite in-memory cho test suite độc lập, chạy cực nhanh
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestingSession() as db:
        # 1. Roles
        role_admin = Role(id=1, name="ADMIN", description="Quản trị viên")
        role_user = Role(id=2, name="USER", description="Khách hàng")
        db.add_all([role_admin, role_user])
        db.flush()

        # 2. Users
        pwd_hash = get_password_hash("password123")
        # User 1: Đã xem phim 1 (có booking đã thanh toán, suất chiếu trong quá khứ)
        u1 = User(id=1, role_id=2, full_name="Nguyen Van A", email="user1@cinema.com", password_hash=pwd_hash, is_active=True)
        # User 2: Đã xem phim 1 (suất chiếu khác trong quá khứ)
        u2 = User(id=2, role_id=2, full_name="Tran Thi B", email="user2@cinema.com", password_hash=pwd_hash, is_active=True)
        # User 3: Chưa từng đặt vé
        u3 = User(id=3, role_id=2, full_name="Le Van C (Chua mua ve)", email="user3@cinema.com", password_hash=pwd_hash, is_active=True)
        # User 4: Có vé nhưng CHƯA thanh toán (GIU_CHO)
        u4 = User(id=4, role_id=2, full_name="Pham D (Chua thanh toan)", email="user4@cinema.com", password_hash=pwd_hash, is_active=True)
        # User 5: Đã thanh toán nhưng SUẤT CHIẾU CHƯA KẾT THÚC (tương lai)
        u5 = User(id=5, role_id=2, full_name="Hoang E (Suat chieu tuong lai)", email="user5@cinema.com", password_hash=pwd_hash, is_active=True)

        db.add_all([u1, u2, u3, u4, u5])
        db.flush()

        # 3. Phim
        # Phim 1: Có nhiều suất chiếu
        m1 = Movie(id=1, title="Mai", duration_minutes=120, release_date=date.today() - timedelta(days=30), status="NOW_SHOWING")
        # Phim 2: Phim mới chưa có đánh giá nào
        m2 = Movie(id=2, title="Dune: Part Two", duration_minutes=166, release_date=date.today(), status="NOW_SHOWING")
        db.add_all([m1, m2])
        db.flush()

        # 4. Rạp & Phòng
        cinema = Cinema(id=1, name="Lumen Cinema Center", address="123 Tran Hung Dao", city="Ha Noi")
        db.add(cinema)
        db.flush()
        room = Room(id=1, cinema_id=1, name="Screen 01", room_type="2D", total_seats=60)
        db.add(room)
        db.flush()

        # 5. Suất chiếu
        # St1: Quá khứ (đã kết thúc hôm qua)
        past_end = datetime.now() - timedelta(hours=2)
        past_start = past_end - timedelta(hours=2)
        st_past = Showtime(id=1, movie_id=1, room_id=1, start_time=past_start, end_time=past_end, price=Decimal("100000.00"))

        # St2: Tương lai (ngày mai)
        future_start = datetime.now() + timedelta(days=1)
        future_end = future_start + timedelta(hours=2)
        st_future = Showtime(id=2, movie_id=1, room_id=1, start_time=future_start, end_time=future_end, price=Decimal("100000.00"))

        db.add_all([st_past, st_future])
        db.flush()

        # 6. Bookings & Payments
        # Booking cho User 1: Đã thanh toán, suất chiếu quá khứ (HỢP LỆ ĐỂ ĐÁNH GIÁ)
        b1 = Booking(id=1, booking_code="BK-0001", user_id=1, showtime_id=1, total_price=Decimal("100000.00"), status="DA_THANH_TOAN")
        p1 = Payment(id=1, booking_id=1, amount=Decimal("100000.00"), payment_method="MOMO", status="SUCCESS")

        # Booking cho User 2: Đã thanh toán, suất chiếu quá khứ (HỢP LỆ ĐỂ ĐÁNH GIÁ)
        b2 = Booking(id=2, booking_code="BK-0002", user_id=2, showtime_id=1, total_price=Decimal("100000.00"), status="DA_THANH_TOAN")
        p2 = Payment(id=2, booking_id=2, amount=Decimal("100000.00"), payment_method="VNPAY", status="SUCCESS")

        # Booking cho User 4: CHƯA THANH TOÁN (GIU_CHO)
        b4 = Booking(id=4, booking_code="BK-0004", user_id=4, showtime_id=1, total_price=Decimal("100000.00"), status="GIU_CHO")

        # Booking cho User 5: Đã thanh toán NHƯNG suất chiếu tương lai
        b5 = Booking(id=5, booking_code="BK-0005", user_id=5, showtime_id=2, total_price=Decimal("100000.00"), status="DA_THANH_TOAN")
        p5 = Payment(id=5, booking_id=5, amount=Decimal("100000.00"), payment_method="MOMO", status="SUCCESS")

        db.add_all([b1, p1, b2, p2, b4, b5, p5])
        db.commit()

    client = TestClient(app)

    tokens = {
        "user1": create_access_token(data={"sub": "1"}),
        "user2": create_access_token(data={"sub": "2"}),
        "user3": create_access_token(data={"sub": "3"}),
        "user4": create_access_token(data={"sub": "4"}),
        "user5": create_access_token(data={"sub": "5"}),
    }

    return client, tokens


def test_1_anonymous_cannot_review(test_setup):
    """1. Khách chưa đăng nhập gửi đánh giá -> 401 Unauthorized"""
    client, _ = test_setup
    res = client.post("/api/movies/1/reviews", json={"rating": 5, "comment": "Phim qua hay!"})
    assert res.status_code == 401


def test_2_user_without_booking_cannot_review(test_setup):
    """2. Khách đã đăng nhập nhưng chưa đặt vé -> 403 Forbidden"""
    client, tokens = test_setup
    headers = {"Authorization": f"Bearer {tokens['user3']}"}
    res = client.post("/api/movies/1/reviews", json={"rating": 5, "comment": "Phim hay lam"}, headers=headers)
    assert res.status_code == 403
    assert "chưa mua vé" in res.json()["detail"].lower()


def test_3_user_unpaid_booking_cannot_review(test_setup):
    """3. Khách có booking nhưng chưa thanh toán -> 403 Forbidden"""
    client, tokens = test_setup
    headers = {"Authorization": f"Bearer {tokens['user4']}"}
    res = client.post("/api/movies/1/reviews", json={"rating": 4, "comment": "Chua thanh toan"}, headers=headers)
    assert res.status_code == 403
    assert "chưa được thanh toán" in res.json()["detail"].lower()


def test_4_user_future_showtime_cannot_review(test_setup):
    """4. Khách đã thanh toán nhưng suất chiếu chưa kết thúc -> 403 Forbidden"""
    client, tokens = test_setup
    headers = {"Authorization": f"Bearer {tokens['user5']}"}
    res = client.post("/api/movies/1/reviews", json={"rating": 5, "comment": "Chua xem xong"}, headers=headers)
    assert res.status_code == 403
    assert "chưa kết thúc" in res.json()["detail"].lower()


def test_5_eligible_user_valid_review(test_setup):
    """5. Khách đã xem phim và gửi đánh giá hợp lệ -> 201 Created"""
    client, tokens = test_setup
    headers = {"Authorization": f"Bearer {tokens['user1']}"}
    res = client.post(
        "/api/movies/1/reviews",
        json={"rating": 5, "comment": "Kịch bản xuất sắc, diễn xuất quá tuyệt vời!"},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["rating"] == 5
    assert data["comment"] == "Kịch bản xuất sắc, diễn xuất quá tuyệt vời!"
    assert data["user_name"] == "Nguyen Van A"
    assert data["is_owner"] is True


def test_6_invalid_ratings_rejected(test_setup):
    """6. Đánh giá 0 sao hoặc trên 5 sao -> 422 Unprocessable Entity"""
    client, tokens = test_setup
    headers = {"Authorization": f"Bearer {tokens['user1']}"}
    # 0 sao
    res0 = client.post("/api/movies/1/reviews", json={"rating": 0, "comment": "0 sao"}, headers=headers)
    assert res0.status_code == 422
    # 6 sao
    res6 = client.post("/api/movies/1/reviews", json={"rating": 6, "comment": "6 sao"}, headers=headers)
    assert res6.status_code == 422


def test_7_empty_comment_rejected(test_setup):
    """7. Bình luận rỗng hoặc chỉ có khoảng trắng -> 422 Unprocessable Entity"""
    client, tokens = test_setup
    headers = {"Authorization": f"Bearer {tokens['user1']}"}
    res_empty = client.post("/api/movies/1/reviews", json={"rating": 4, "comment": "   "}, headers=headers)
    assert res_empty.status_code == 422


def test_8_duplicate_review_updates_existing(test_setup):
    """8. Đánh giá trùng -> Hệ thống tự động cập nhật đánh giá (200 OK, không duplicate)"""
    client, tokens = test_setup
    headers = {"Authorization": f"Bearer {tokens['user1']}"}
    # Gửi lại đánh giá mới với 4 sao và lời bình khác
    res = client.post(
        "/api/movies/1/reviews",
        json={"rating": 4, "comment": "Xem lại lần 2 thấy vẫn hay nhưng có chút sạn."},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["rating"] == 4
    assert data["comment"] == "Xem lại lần 2 thấy vẫn hay nhưng có chút sạn."

    # Kiểm tra tổng số đánh giá của phim vẫn chỉ có 1
    res_list = client.get("/api/movies/1/reviews")
    assert res_list.status_code == 200
    assert res_list.json()["total_reviews"] == 1


def test_9_two_users_review_same_movie(test_setup):
    """9. Hai khách hàng đánh giá cùng một phim -> Lưu 2 đánh giá riêng biệt"""
    client, tokens = test_setup
    headers = {"Authorization": f"Bearer {tokens['user2']}"}
    res = client.post(
        "/api/movies/1/reviews",
        json={"rating": 5, "comment": "Bộ phim xúc động nghẹn ngào, đáng đồng tiền bát gạo!"},
        headers=headers,
    )
    assert res.status_code == 201

    res_list = client.get("/api/movies/1/reviews")
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["total_reviews"] == 2
    assert len(data["items"]) == 2


def test_10_average_rating_calculated_accurately(test_setup):
    """10. Điểm trung bình sau khi có nhiều đánh giá được tính toán chính xác (4 + 5 = 4.5)"""
    client, _ = test_setup
    res = client.get("/api/movies/1/reviews")
    data = res.json()
    # User 1: 4 sao, User 2: 5 sao -> trung bình = 4.5
    assert data["average_rating"] == 4.5
    assert data["total_reviews"] == 2
    assert data["rating_breakdown"]["5"] == 1
    assert data["rating_breakdown"]["4"] == 1
    assert data["rating_breakdown"]["3"] == 0


def test_11_movie_without_reviews(test_setup):
    """11. Phim chưa có đánh giá -> Trả về 0.0 sao, 0 lượt, danh sách rỗng"""
    client, _ = test_setup
    res = client.get("/api/movies/2/reviews")
    assert res.status_code == 200
    data = res.json()
    assert data["average_rating"] == 0.0
    assert data["total_reviews"] == 0
    assert len(data["items"]) == 0


def test_12_eligibility_api(test_setup):
    """12. Kiểm tra API xác minh điều kiện đánh giá /api/movies/{id}/reviews/eligibility"""
    client, tokens = test_setup

    # User 1 đã xem và đã đánh giá
    res1 = client.get("/api/movies/1/reviews/eligibility", headers={"Authorization": f"Bearer {tokens['user1']}"})
    assert res1.status_code == 200
    assert res1.json()["can_review"] is True
    assert res1.json()["has_reviewed"] is True
    assert res1.json()["existing_review"] is not None

    # User 3 chưa mua vé
    res3 = client.get("/api/movies/1/reviews/eligibility", headers={"Authorization": f"Bearer {tokens['user3']}"})
    assert res3.status_code == 200
    assert res3.json()["can_review"] is False
    assert res3.json()["has_reviewed"] is False


def test_13_movie_detail_includes_rating(test_setup):
    """13. API chi tiết phim GET /api/movies/{id} tích hợp điểm trung bình và tổng lượt đánh giá"""
    client, _ = test_setup
    res = client.get("/api/movies/1")
    assert res.status_code == 200
    data = res.json()
    assert data["average_rating"] == 4.5
    assert data["total_reviews"] == 2
