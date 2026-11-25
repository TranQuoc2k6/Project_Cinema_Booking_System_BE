"""
Unit tests kiểm thử toàn diện 11 quy định đặt vé (Rules 1 - 11).
Tập trung đặc biệt vào các quy định mới được hoàn thiện:
- Rule 1: Khách hàng phải chọn phim đang được phép bán vé (chặn phim ENDED / COMING_SOON chưa tới ngày).
- Rule 2: Chỉ được đặt vé cho suất chiếu còn hiệu lực và chưa bắt đầu (chặn suất chiếu quá khứ).
- Rule 4: Khách hàng chỉ được chọn ghế còn trống và còn hoạt động (is_active).
- Rule 9: Mỗi vé được cấp mã vé riêng để kiểm tra khi vào rạp (TK-{booking_code}-{seat_number}).
- Rule 11: Khi đặt 2 vé, 2 vé phải được đặt cạnh nhau và không được có ghế trống xen giữa.
"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
from app.core.dependencies import get_current_user
from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.models.room import Room
from app.models.cinema import Cinema
from app.models.movie import Movie
from app.models.user import User
from app.models.role import Role

# In-memory SQLite for testing
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
client = TestClient(app)


@pytest.fixture
def db_session():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    session = TestSession()

    user_role = Role(id=1, name="USER", description="Khách hàng")
    admin_role = Role(id=2, name="ADMIN", description="Quản trị viên")
    session.add_all([user_role, admin_role])

    user = User(id=1, full_name="Nguyễn Văn Test", email="test@cinema.com", password_hash="hash", role_id=1)
    session.add(user)

    movie_active = Movie(
        id=1,
        title="Dune 2",
        release_date=date.today() - timedelta(days=10),
        status="NOW_SHOWING",
        duration_minutes=150,
    )
    movie_ended = Movie(
        id=2,
        title="Phim Đã Hết Chiếu",
        release_date=date.today() - timedelta(days=60),
        status="ENDED",
        duration_minutes=120,
    )
    movie_coming_soon = Movie(
        id=3,
        title="Avatar 3 Chưa Chiếu",
        release_date=date.today() + timedelta(days=30),
        status="COMING_SOON",
        duration_minutes=180,
    )
    session.add_all([movie_active, movie_ended, movie_coming_soon])

    cinema = Cinema(id=1, name="CGV Landmark 81", address="Bình Thạnh", city="TP.HCM")
    session.add(cinema)

    room = Room(id=1, cinema_id=1, name="Phòng 01", room_type="2D")
    session.add(room)
    session.flush()

    # Tạo hàng ghế A (1-10) và B (1-10). Ghế A09 (id=9) bị hỏng (is_active=False)
    for col in range(1, 11):
        is_act = (col != 9)
        s_a = Seat(id=col, room_id=1, seat_row="A", seat_column=col, seat_number=f"A{col:02d}", seat_type="standard", is_active=is_act)
        s_b = Seat(id=10 + col, room_id=1, seat_row="B", seat_column=col, seat_number=f"B{col:02d}", seat_type="vip", is_active=True)
        session.add_all([s_a, s_b])
    session.flush()

    # Suất chiếu tương lai hợp lệ (bắt đầu sau 2 tiếng)
    st_valid = Showtime(
        id=1,
        movie_id=1,
        room_id=1,
        start_time=datetime.utcnow() + timedelta(hours=2),
        end_time=datetime.utcnow() + timedelta(hours=4),
        price=Decimal("100000"),
    )
    # Suất chiếu đã bắt đầu trong quá khứ (bắt đầu cách đây 1 tiếng)
    st_past = Showtime(
        id=2,
        movie_id=1,
        room_id=1,
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow() + timedelta(hours=1),
        price=Decimal("100000"),
    )
    # Suất chiếu gắn với phim đã ngừng chiếu (ENDED)
    st_ended_movie = Showtime(
        id=3,
        movie_id=2,
        room_id=1,
        start_time=datetime.utcnow() + timedelta(hours=3),
        end_time=datetime.utcnow() + timedelta(hours=5),
        price=Decimal("100000"),
    )
    # Suất chiếu gắn với phim COMING_SOON chưa đến ngày
    st_future_movie = Showtime(
        id=4,
        movie_id=3,
        room_id=1,
        start_time=datetime.utcnow() + timedelta(hours=3),
        end_time=datetime.utcnow() + timedelta(hours=6),
        price=Decimal("100000"),
    )
    session.add_all([st_valid, st_past, st_ended_movie, st_future_movie])
    session.commit()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: session.query(User).filter(User.id == 1).first()

    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)


def auth_headers():
    return {"Authorization": "Bearer dummy_token"}


# ============================================================================
# TEST RULE 1: CHỌN PHIM ĐƯỢC PHÉP BÁN VÉ
# ============================================================================

def test_rule_1_reject_booking_ended_movie(db_session):
    """Rule 1: Từ chối đặt vé khi phim đã ngừng chiếu (ENDED)."""
    # st_ended_movie (id=3) gắn với phim có status="ENDED"
    payload = {"showtime_id": 3, "seat_ids": [1, 2]}
    resp = client.post("/api/bookings/hold", json=payload, headers=auth_headers())
    assert resp.status_code == 400
    assert "ngừng chiếu" in resp.json()["detail"]


def test_rule_1_reject_booking_unreleased_movie(db_session):
    """Rule 1: Từ chối đặt vé khi phim COMING_SOON chưa đến ngày khởi chiếu."""
    payload = {"showtime_id": 4, "seat_ids": [1, 2]}
    resp = client.post("/api/bookings/hold", json=payload, headers=auth_headers())
    assert resp.status_code == 400
    assert "chưa đến ngày khởi chiếu" in resp.json()["detail"]


# ============================================================================
# TEST RULE 2: CHỌN SUẤT CHIẾU CÒN HIỆU LỰC & CHƯA BẮT ĐẦU
# ============================================================================

def test_rule_2_reject_booking_past_or_started_showtime(db_session):
    """Rule 2: Từ chối giữ ghế cho suất chiếu đã bắt đầu hoặc trong quá khứ."""
    # st_past (id=2) đã bắt đầu cách đây 1 giờ
    payload = {"showtime_id": 2, "seat_ids": [1, 2]}
    resp = client.post("/api/bookings/hold", json=payload, headers=auth_headers())
    assert resp.status_code == 400
    assert "đã bắt đầu" in resp.json()["detail"] or "quá thời gian" in resp.json()["detail"]


# ============================================================================
# TEST RULE 4: CHỈ ĐƯỢC CHỌN GHẾ CÒN TRỐNG & HOẠT ĐỘNG
# ============================================================================

def test_rule_4_reject_inactive_seat(db_session):
    """Rule 4: Từ chối đặt ghế đang bảo trì hoặc hỏng (is_active=False)."""
    # A09 (id=9) is_active=False
    payload = {"showtime_id": 1, "seat_ids": [8, 9]}
    resp = client.post("/api/bookings/hold", json=payload, headers=auth_headers())
    assert resp.status_code == 400
    assert "tạm ngừng hoạt động" in resp.json()["detail"] or "bảo trì" in resp.json()["detail"]


# ============================================================================
# TEST RULE 9: MÃ VÉ RIÊNG CHO TỪNG GHẾ (TK-{booking_code}-{seat_number})
# ============================================================================

def test_rule_9_ticket_code_for_each_seat(db_session):
    """Rule 9: Mỗi ghế được cấp mã vé riêng và có thể tra cứu/soát vé qua mã vé con."""
    # Đặt 2 ghế hợp lệ A01, A02
    payload = {"showtime_id": 1, "seat_ids": [1, 2]}
    resp = client.post("/api/bookings/hold", json=payload, headers=auth_headers())
    assert resp.status_code == 201
    booking_id = resp.json()["id"]

    # Xác nhận thanh toán
    confirm_resp = client.post(f"/api/bookings/{booking_id}/confirm", headers=auth_headers())
    assert confirm_resp.status_code == 200

    # Lấy chi tiết vé
    ticket_resp = client.get(f"/api/tickets/{booking_id}", headers=auth_headers())
    assert ticket_resp.status_code == 200
    t_data = ticket_resp.json()

    # Kiểm tra mỗi ghế trong vé có ticket_code riêng biệt
    seats = t_data["seats"]
    assert len(seats) == 2
    assert seats[0]["ticket_code"] is not None
    assert seats[1]["ticket_code"] is not None
    assert seats[0]["ticket_code"] != seats[1]["ticket_code"]
    assert "TK-" in seats[0]["ticket_code"]
    assert "A01" in seats[0]["ticket_code"]
    assert "A02" in seats[1]["ticket_code"]

    # Tra cứu vé bằng mã vé riêng của ghế 1
    tkt_code_1 = seats[0]["ticket_code"]
    verify_resp = client.get(f"/api/bookings/ticket-check/{tkt_code_1}")
    assert verify_resp.status_code == 200
    assert verify_resp.json()["booking_id"] == booking_id


# ============================================================================
# TEST RULE 11: 2 VÉ CẠNH NHAU & KHÔNG CÓ GHẾ TRỐNG XEN GIỮA
# ============================================================================

def test_rule_11_two_seats_in_different_rows_rejected(db_session):
    """Rule 11: Đặt 2 vé ở 2 hàng khác nhau (A01 và B01) bị từ chối."""
    payload = {"showtime_id": 1, "seat_ids": [1, 11]}  # A01 (id=1), B01 (id=11)
    resp = client.post("/api/bookings/hold", json=payload, headers=auth_headers())
    assert resp.status_code == 400
    assert "cùng một hàng" in resp.json()["detail"]


def test_rule_11_two_seats_with_gap_rejected(db_session):
    """Rule 11: Đặt 2 vé cùng hàng nhưng có ghế trống xen giữa (A01 và A03) bị từ chối."""
    payload = {"showtime_id": 1, "seat_ids": [1, 3]}  # A01 (id=1) và A03 (id=3), bỏ trống A02
    resp = client.post("/api/bookings/hold", json=payload, headers=auth_headers())
    assert resp.status_code == 400
    assert "cạnh nhau" in resp.json()["detail"] and "xen giữa" in resp.json()["detail"]


def test_rule_11_two_seats_adjacent_success(db_session):
    """Rule 11: Đặt 2 vé cạnh nhau (A01 và A02) thành công."""
    payload = {"showtime_id": 1, "seat_ids": [1, 2]}  # A01 và A02
    resp = client.post("/api/bookings/hold", json=payload, headers=auth_headers())
    assert resp.status_code == 201
    assert resp.json()["status"] == "GIU_CHO"


def test_rule_11_three_seats_with_gap_in_row_rejected(db_session):
    """Rule 11: Đặt 3 vé trong cùng hàng nhưng có khoảng trống xen giữa (A01, A02, A04) bị từ chối."""
    payload = {"showtime_id": 1, "seat_ids": [1, 2, 4]}  # bỏ trống A03
    resp = client.post("/api/bookings/hold", json=payload, headers=auth_headers())
    assert resp.status_code == 400
    assert "liền kề" in resp.json()["detail"] or "xen giữa" in resp.json()["detail"]


def test_rule_11_two_adjacent_middle_seats_success(db_session):
    """Rule 11: Đặt 2 vé cạnh nhau ở giữa hàng (A02 và A03) thành công bình thường."""
    payload = {"showtime_id": 1, "seat_ids": [2, 3]}  # A02 và A03
    resp = client.post("/api/bookings/hold", json=payload, headers=auth_headers())
    assert resp.status_code == 201
    assert resp.json()["status"] == "GIU_CHO"
