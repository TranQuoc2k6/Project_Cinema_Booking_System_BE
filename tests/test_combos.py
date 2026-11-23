"""
Unit tests cho Task T3C72E6:
  [Bonus] Combo bắp nước:
  - Chọn combo khi đặt vé, cộng vào tổng tiền
  - Admin quản lý combo (CRUD)
  - Validate giá tiền và số lượng ở server
"""
from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.combo import Combo
from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.booking_combo import BookingCombo
from app.models.cinema import Cinema
from app.models.movie import Movie
from app.models.room import Room
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.models.user import User
from app.models.role import Role
from app.schemas.combo import ComboCreate, ComboUpdate, BookingComboItemRequest
from app.services import combo_service, booking_service


@pytest.fixture
def db():
    from database import Base
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Seed Roles & Users
    user_role = Role(id=1, name="USER", description="Khách hàng")
    admin_role = Role(id=2, name="ADMIN", description="Quản trị viên")
    session.add_all([user_role, admin_role])
    session.flush()

    user = User(id=1, full_name="Nguyễn Đình Đức", email="duc@cinema.com", password_hash="hash", role_id=1)
    admin = User(id=2, full_name="Admin Rạp", email="admin@cinema.com", password_hash="hash", role_id=2)
    session.add_all([user, admin])
    session.flush()

    # 2. Cinema, Room, Seats, Movie, Showtime
    cinema = Cinema(id=1, name="LUMEN Vincom", address="Hà Nội", city="Hà Nội")
    session.add(cinema)
    session.flush()

    room = Room(id=1, cinema_id=1, name="Phòng 01", total_seats=10, room_type="2D")
    session.add(room)
    session.flush()

    seat1 = Seat(id=1, room_id=1, seat_row="A", seat_column=1, seat_number="A01", seat_type="standard", is_active=True)
    seat2 = Seat(id=2, room_id=1, seat_row="A", seat_column=2, seat_number="A02", seat_type="vip", is_active=True)
    session.add_all([seat1, seat2])
    session.flush()

    movie = Movie(id=1, title="Mai", slug="mai", duration_minutes=131, release_date=datetime.utcnow().date(), status="NOW_SHOWING")
    session.add(movie)
    session.flush()

    showtime = Showtime(
        id=1,
        movie_id=1,
        room_id=1,
        start_time=datetime.utcnow() + timedelta(hours=3),
        end_time=datetime.utcnow() + timedelta(hours=5),
        price=Decimal("100000.00"),
    )
    session.add(showtime)
    session.flush()

    # 3. Seed sample Combos
    c1 = Combo(id=1, name="Combo Solo", description="1 Bắp ngọt + 1 Nước ngọt", price=Decimal("79000.00"), is_active=True)
    c2 = Combo(id=2, name="Combo Couple", description="1 Bắp phô mai + 2 Nước ngọt", price=Decimal("109000.00"), is_active=True)
    c3 = Combo(id=3, name="Combo Ngưng Bán", description="Món cũ", price=Decimal("50000.00"), is_active=False)
    session.add_all([c1, c2, c3])
    session.commit()

    yield session
    session.close()


class TestComboManagementAndBooking:

    def test_get_active_combos_only_returns_active(self, db):
        """Khách hàng chỉ thấy các combo đang mở bán (is_active=True)"""
        combos = combo_service.get_active_combos(db)
        assert len(combos) == 2
        assert all(c.is_active is True for c in combos)
        names = [c.name for c in combos]
        assert "Combo Solo" in names
        assert "Combo Couple" in names
        assert "Combo Ngưng Bán" not in names

    def test_admin_create_combo_success(self, db):
        """Admin tạo combo bắp nước mới thành công"""
        data = ComboCreate(
            name="Combo Gia Đình Siêu To",
            description="2 Bắp khổng lồ + 4 Nước + 2 Xúc xích",
            price=Decimal("199000.00"),
            image_url="https://example.com/family.jpg",
            is_active=True,
        )
        new_combo = combo_service.create_combo(db, data)
        assert new_combo.id is not None
        assert new_combo.name == "Combo Gia Đình Siêu To"
        assert new_combo.price == Decimal("199000.00")

    def test_admin_create_combo_duplicate_name_fails(self, db):
        """Admin tạo combo trùng tên -> Báo lỗi 400"""
        data = ComboCreate(
            name="Combo Solo",  # Đã có trong DB
            price=Decimal("80000.00"),
        )
        with pytest.raises(HTTPException) as exc_info:
            combo_service.create_combo(db, data)
        assert exc_info.value.status_code == 400
        assert "Đã tồn tại combo" in exc_info.value.detail

    def test_admin_update_combo(self, db):
        """Admin cập nhật giá và mô tả của combo"""
        update_data = ComboUpdate(
            price=Decimal("89000.00"),
            description="1 Bắp phô mai lớn + 1 Nước ngọt"
        )
        updated = combo_service.update_combo(db, 1, update_data)
        assert updated.price == Decimal("89000.00")
        assert updated.description == "1 Bắp phô mai lớn + 1 Nước ngọt"
        assert updated.name == "Combo Solo"  # Giữ nguyên

    def test_admin_delete_unused_combo(self, db):
        """Admin xóa combo chưa có đơn vé -> Xóa hoàn toàn khỏi CSDL"""
        res = combo_service.delete_combo(db, 3)
        assert res["success"] is True
        assert res["soft_deleted"] is False
        assert db.query(Combo).filter(Combo.id == 3).first() is None

    def test_booking_hold_with_combos_calculates_total_price(self, db):
        """
        Chọn combo khi đặt vé:
        - Ghế Standard (100k) + 1 Combo Solo (79k) + 2 Combo Couple (109k x 2 = 218k)
        - Tổng tiền mong đợi: 100k + 79k + 218k = 397,000 đ
        """
        combos_req = [
            BookingComboItemRequest(combo_id=1, quantity=1),
            BookingComboItemRequest(combo_id=2, quantity=2),
        ]
        booking = booking_service.hold_seats(
            showtime_id=1,
            seat_ids=[1],  # Ghế A01 Standard (100k)
            user_id=1,
            db=db,
            combos=combos_req,
        )

        assert booking.status == "GIU_CHO"
        expected_total = Decimal("100000.00") + Decimal("79000.00") + (Decimal("109000.00") * 2)
        assert booking.total_price == expected_total

        # Kiểm tra BookingCombo đã được lưu
        bcs = db.query(BookingCombo).filter(BookingCombo.booking_id == booking.id).all()
        assert len(bcs) == 2
        quantities = {bc.combo_id: bc.quantity for bc in bcs}
        assert quantities[1] == 1
        assert quantities[2] == 2

    def test_booking_confirm_recalculates_price_including_combos(self, db):
        """Xác nhận đặt vé: Server tự động tính lại giá ghế và cộng tiền combo"""
        combos_req = [BookingComboItemRequest(combo_id=1, quantity=1)]
        booking = booking_service.hold_seats(
            showtime_id=1,
            seat_ids=[1],
            user_id=1,
            db=db,
            combos=combos_req,
        )

        user = db.query(User).get(1)
        res = booking_service.confirm_booking(
            db=db,
            user=user,
            booking_id=booking.id,
            payment_method="MOMO",
        )

        assert res["success"] is True
        # Ghế A01 Standard (100k) + Combo Solo (79k) = 179k
        assert res["recalculated_price"] == Decimal("179000.00")
        assert res["booking"].total_price == Decimal("179000.00")

    def test_booking_with_inactive_combo_rejected(self, db):
        """Cố tình đặt combo đã ngưng bán -> Báo lỗi 400"""
        combos_req = [BookingComboItemRequest(combo_id=3, quantity=1)]  # Combo 3 ngưng bán
        with pytest.raises(HTTPException) as exc_info:
            booking_service.hold_seats(
                showtime_id=1,
                seat_ids=[1],
                user_id=1,
                db=db,
                combos=combos_req,
            )
        assert exc_info.value.status_code == 400
        assert "tạm ngừng kinh doanh" in exc_info.value.detail

    def test_ticket_detail_contains_combo_info(self, db):
        """Vé điện tử hiển thị danh sách combo bắp nước đã đặt"""
        combos_req = [BookingComboItemRequest(combo_id=1, quantity=2)]
        booking = booking_service.hold_seats(
            showtime_id=1,
            seat_ids=[1],
            user_id=1,
            db=db,
            combos=combos_req,
        )

        user = db.query(User).get(1)
        ticket_detail = booking_service.get_booking_detail_for_user(
            db=db,
            user=user,
            booking_id=booking.id,
        )

        assert "combos" in ticket_detail
        assert len(ticket_detail["combos"]) == 1
        assert ticket_detail["combos"][0]["name"] == "Combo Solo"
        assert ticket_detail["combos"][0]["quantity"] == 2
        assert ticket_detail["combos"][0]["total_price"] == Decimal("158000.00")
