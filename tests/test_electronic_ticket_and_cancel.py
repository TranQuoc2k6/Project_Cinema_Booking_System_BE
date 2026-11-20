"""
Unit tests cho Task T3C6D1A:
  [Vé] Vé điện tử và huỷ vé:
  - Trang vé sau khi đặt: mã vé, phim, rạp, phòng, ghế, giờ
  - Khách huỷ được vé trước giờ chiếu 2 tiếng (trả ghế)
"""
from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.cinema import Cinema
from app.models.movie import Movie
from app.models.payment import Payment
from app.models.role import Role
from app.models.room import Room
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.models.user import User
from app.services.booking_service import (
    format_ticket_response,
    get_booking_detail_for_user,
    get_user_bookings,
    user_cancel_booking,
)


@pytest.fixture
def in_memory_db():
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

    user_a = User(
        id=1,
        full_name="Nguyễn Văn A",
        email="user_a@cinema.com",
        phone="0987654321",
        password_hash="fakehash",
        role_id=1,
    )
    user_b = User(
        id=2,
        full_name="Trần Thị B",
        email="user_b@cinema.com",
        phone="0912345678",
        password_hash="fakehash",
        role_id=1,
    )
    session.add_all([user_a, user_b])
    session.flush()

    # 2. Seed Cinema, Room, Seat
    cinema = Cinema(id=1, name="LUMEN Mega Mall", address="123 Cầu Giấy", city="Hà Nội")
    session.add(cinema)
    session.flush()

    room = Room(id=1, cinema_id=1, name="Cinema 01 - Laser", room_type="2D", total_seats=20)
    session.add(room)
    session.flush()

    seat1 = Seat(id=1, room_id=1, seat_number="E05", seat_row="E", seat_column=5, seat_type="standard")
    seat2 = Seat(id=2, room_id=1, seat_number="E06", seat_row="E", seat_column=6, seat_type="vip")
    seat3 = Seat(id=3, room_id=1, seat_number="F01", seat_row="F", seat_column=1, seat_type="standard")
    session.add_all([seat1, seat2, seat3])
    session.flush()

    # 3. Seed Movie
    movie = Movie(
        id=1,
        title="Dune: Hành Tinh Cát - Phần 2",
        duration_minutes=166,
        poster_url="https://image.url/poster.jpg",
        release_date=datetime.now().date(),
    )
    session.add(movie)
    session.flush()

    yield {
        "session": session,
        "user_a": user_a,
        "user_b": user_b,
        "movie": movie,
        "room": room,
        "seats": [seat1, seat2, seat3],
        "cinema": cinema,
    }

    session.close()


class TestUserCancelBookingAndReleaseSeats:
    """Kiểm thử nghiệp vụ hủy vé & giải phóng ghế (Task T3C6D1A)"""

    def test_cancel_booking_success_more_than_2_hours_before_showtime(self, in_memory_db):
        """Khách hủy vé trước giờ chiếu > 2 tiếng -> Thành công, giải phóng ghế và đổi trạng thái sang DA_HUY"""
        session = in_memory_db["session"]
        user = in_memory_db["user_a"]
        movie = in_memory_db["movie"]
        room = in_memory_db["room"]
        seat1, seat2 = in_memory_db["seats"][0], in_memory_db["seats"][1]

        # Suất chiếu diễn ra sau 4 tiếng nữa (hợp lệ > 2h)
        showtime = Showtime(
            id=10,
            movie_id=movie.id,
            room_id=room.id,
            start_time=datetime.utcnow() + timedelta(hours=4),
            end_time=datetime.utcnow() + timedelta(hours=6, minutes=46),
            price=Decimal("100000"),
        )
        session.add(showtime)
        session.flush()

        booking = Booking(
            id=101,
            booking_code="BK-20261120-T3C6D1A",
            user_id=user.id,
            showtime_id=showtime.id,
            total_price=Decimal("200000"),
            status="DA_THANH_TOAN",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(booking)
        session.flush()

        # Giữ 2 ghế trong BookingSeat
        bs1 = BookingSeat(booking_id=booking.id, showtime_id=showtime.id, seat_id=seat1.id, price=Decimal("100000"))
        bs2 = BookingSeat(booking_id=booking.id, showtime_id=showtime.id, seat_id=seat2.id, price=Decimal("100000"))
        session.add_all([bs1, bs2])

        # Thanh toán tương ứng
        payment = Payment(
            booking_id=booking.id,
            amount=Decimal("200000"),
            payment_method="MOMO",
            status="success",
        )
        session.add(payment)
        session.commit()

        # Kiểm tra trước khi hủy: có 2 ghế đang bị chiếm
        active_seats_before = session.query(BookingSeat).filter(BookingSeat.showtime_id == showtime.id).count()
        assert active_seats_before == 2

        # Thực hiện hủy vé
        result = user_cancel_booking(db=session, user=user, booking_id=booking.id)

        assert result["success"] is True
        assert result["booking_id"] == 101
        assert result["new_status"] == "DA_HUY"
        assert set(result["released_seats"]) == {"E05", "E06"}
        assert result["refund_status"] == "REFUNDED"

        # Kiểm tra DB sau khi hủy
        session.refresh(booking)
        assert booking.status == "DA_HUY"
        assert booking.held_until is None

        # Rất quan trọng: Toàn bộ BookingSeat phải bị xóa để trả ghế (ghế trống)
        active_seats_after = session.query(BookingSeat).filter(BookingSeat.showtime_id == showtime.id).count()
        assert active_seats_after == 0, "Ghế phải được giải phóng hoàn toàn khỏi suất chiếu"

        # Payment chuyển sang refunded
        session.refresh(payment)
        assert payment.status == "refunded"

    def test_cancel_booking_fails_when_less_than_2_hours_before_showtime(self, in_memory_db):
        """Khách cố hủy vé khi chỉ còn 1 tiếng trước giờ chiếu -> Bị từ chối với 400 Bad Request"""
        session = in_memory_db["session"]
        user = in_memory_db["user_a"]
        movie = in_memory_db["movie"]
        room = in_memory_db["room"]
        seat1 = in_memory_db["seats"][0]

        # Suất chiếu diễn ra sau 1 tiếng (không đủ điều kiện >= 2h)
        showtime = Showtime(
            id=20,
            movie_id=movie.id,
            room_id=room.id,
            start_time=datetime.utcnow() + timedelta(hours=1),
            end_time=datetime.utcnow() + timedelta(hours=3),
            price=Decimal("100000"),
        )
        session.add(showtime)
        session.flush()

        booking = Booking(
            id=102,
            booking_code="BK-URGENT-001",
            user_id=user.id,
            showtime_id=showtime.id,
            total_price=Decimal("100000"),
            status="DA_THANH_TOAN",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(booking)
        session.flush()

        bs = BookingSeat(booking_id=booking.id, showtime_id=showtime.id, seat_id=seat1.id, price=Decimal("100000"))
        session.add(bs)
        session.commit()

        # Gọi hủy vé -> phải ném HTTPException 400
        with pytest.raises(HTTPException) as excinfo:
            user_cancel_booking(db=session, user=user, booking_id=booking.id)

        assert excinfo.value.status_code == 400
        assert "trước giờ chiếu ít nhất 2 tiếng" in excinfo.value.detail

        # Đảm bảo đơn vé và ghế không bị ảnh hưởng
        session.refresh(booking)
        assert booking.status == "DA_THANH_TOAN"
        assert session.query(BookingSeat).filter(BookingSeat.booking_id == booking.id).count() == 1

    def test_cancel_booking_fails_when_showtime_has_passed(self, in_memory_db):
        """Khách cố hủy vé khi suất chiếu đã diễn ra hoặc đã kết thúc -> Bị từ chối"""
        session = in_memory_db["session"]
        user = in_memory_db["user_a"]
        movie = in_memory_db["movie"]
        room = in_memory_db["room"]
        seat1 = in_memory_db["seats"][0]

        # Suất chiếu đã bắt đầu cách đây 30 phút
        showtime = Showtime(
            id=30,
            movie_id=movie.id,
            room_id=room.id,
            start_time=datetime.utcnow() - timedelta(minutes=30),
            end_time=datetime.utcnow() + timedelta(hours=1, minutes=30),
            price=Decimal("100000"),
        )
        session.add(showtime)
        session.flush()

        booking = Booking(
            id=103,
            booking_code="BK-PAST-001",
            user_id=user.id,
            showtime_id=showtime.id,
            total_price=Decimal("100000"),
            status="DA_THANH_TOAN",
            created_at=datetime.utcnow() - timedelta(hours=2),
            updated_at=datetime.utcnow() - timedelta(hours=2),
        )
        session.add(booking)
        session.flush()

        bs = BookingSeat(booking_id=booking.id, showtime_id=showtime.id, seat_id=seat1.id, price=Decimal("100000"))
        session.add(bs)
        session.commit()

        with pytest.raises(HTTPException) as excinfo:
            user_cancel_booking(db=session, user=user, booking_id=booking.id)

        assert excinfo.value.status_code == 400
        assert "trước giờ chiếu ít nhất 2 tiếng" in excinfo.value.detail

    def test_cancel_already_cancelled_booking_fails(self, in_memory_db):
        """Hủy đơn vé đã bị hủy trước đó -> 400 Bad Request"""
        session = in_memory_db["session"]
        user = in_memory_db["user_a"]
        movie = in_memory_db["movie"]
        room = in_memory_db["room"]

        showtime = Showtime(
            id=40,
            movie_id=movie.id,
            room_id=room.id,
            start_time=datetime.utcnow() + timedelta(hours=5),
            end_time=datetime.utcnow() + timedelta(hours=7),
            price=Decimal("100000"),
        )
        session.add(showtime)
        session.flush()

        booking = Booking(
            id=104,
            booking_code="BK-CANCELLED-ALREADY",
            user_id=user.id,
            showtime_id=showtime.id,
            total_price=Decimal("100000"),
            status="DA_HUY",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(booking)
        session.commit()

        with pytest.raises(HTTPException) as excinfo:
            user_cancel_booking(db=session, user=user, booking_id=booking.id)

        assert excinfo.value.status_code == 400
        assert "đã được hủy trước đó" in excinfo.value.detail

    def test_user_cannot_cancel_others_booking(self, in_memory_db):
        """Khách hàng B không thể hủy vé của khách hàng A -> 403 Forbidden"""
        session = in_memory_db["session"]
        user_a = in_memory_db["user_a"]
        user_b = in_memory_db["user_b"]
        movie = in_memory_db["movie"]
        room = in_memory_db["room"]
        seat1 = in_memory_db["seats"][0]

        showtime = Showtime(
            id=50,
            movie_id=movie.id,
            room_id=room.id,
            start_time=datetime.utcnow() + timedelta(hours=10),
            end_time=datetime.utcnow() + timedelta(hours=12),
            price=Decimal("100000"),
        )
        session.add(showtime)
        session.flush()

        booking = Booking(
            id=105,
            booking_code="BK-USER-A-TICKET",
            user_id=user_a.id,
            showtime_id=showtime.id,
            total_price=Decimal("100000"),
            status="DA_THANH_TOAN",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(booking)
        session.flush()

        bs = BookingSeat(booking_id=booking.id, showtime_id=showtime.id, seat_id=seat1.id, price=Decimal("100000"))
        session.add(bs)
        session.commit()

        # user_b cố hủy vé của user_a
        with pytest.raises(HTTPException) as excinfo:
            user_cancel_booking(db=session, user=user_b, booking_id=booking.id)

        assert excinfo.value.status_code == 403
        assert "không có quyền thao tác" in excinfo.value.detail


class TestElectronicTicketDetailAndListing:
    """Kiểm thử thông tin vé điện tử sau khi đặt & danh sách vé (Task T3C6D1A)"""

    def test_electronic_ticket_detail_contains_all_required_fields(self, in_memory_db):
        """Vé điện tử phải chứa đầy đủ: mã vé, phim, rạp, phòng, ghế, giờ, điều kiện hủy"""
        session = in_memory_db["session"]
        user = in_memory_db["user_a"]
        movie = in_memory_db["movie"]
        room = in_memory_db["room"]
        cinema = in_memory_db["cinema"]
        seat1 = in_memory_db["seats"][0]

        start_time = datetime.utcnow() + timedelta(hours=5)
        showtime = Showtime(
            id=60,
            movie_id=movie.id,
            room_id=room.id,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=166),
            price=Decimal("120000"),
        )
        session.add(showtime)
        session.flush()

        booking = Booking(
            id=201,
            booking_code="BK-E-TICKET-DETAIL",
            user_id=user.id,
            showtime_id=showtime.id,
            total_price=Decimal("120000"),
            status="DA_THANH_TOAN",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(booking)
        session.flush()

        bs = BookingSeat(booking_id=booking.id, showtime_id=showtime.id, seat_id=seat1.id, price=Decimal("120000"))
        session.add(bs)
        session.commit()

        # Lấy chi tiết vé điện tử theo ID
        ticket_detail = get_booking_detail_for_user(db=session, user=user, booking_id=booking.id)

        assert ticket_detail["booking_code"] == "BK-E-TICKET-DETAIL"
        assert ticket_detail["showtime"]["movie"]["title"] == "Dune: Hành Tinh Cát - Phần 2"
        assert ticket_detail["showtime"]["cinema"]["name"] == "LUMEN Mega Mall"
        assert ticket_detail["showtime"]["room_name"] == "Cinema 01 - Laser"
        assert ticket_detail["showtime"]["start_time"] == start_time
        assert len(ticket_detail["seats"]) == 1
        assert ticket_detail["seats"][0]["seat_number"] == "E05"

        # Cờ điều kiện hủy vé
        assert ticket_detail["can_cancel"] is True
        assert ticket_detail["cancel_deadline"] == start_time - timedelta(hours=2)
        assert ticket_detail["cancel_reason"] is None

        # Lấy chi tiết vé theo booking_code
        by_code = get_booking_detail_for_user(db=session, user=user, booking_code="BK-E-TICKET-DETAIL")
        assert by_code["id"] == 201

    def test_my_tickets_listing_displays_can_cancel_flag(self, in_memory_db):
        """Danh sách Vé Của Tôi phản ánh chính xác trạng thái và khả năng hủy vé"""
        session = in_memory_db["session"]
        user = in_memory_db["user_a"]
        movie = in_memory_db["movie"]
        room = in_memory_db["room"]
        seat1, seat2 = in_memory_db["seats"][0], in_memory_db["seats"][1]

        # Vé 1: Chiếu sau 6 tiếng -> can_cancel = True
        st1 = Showtime(
            id=71,
            movie_id=movie.id,
            room_id=room.id,
            start_time=datetime.utcnow() + timedelta(hours=6),
            end_time=datetime.utcnow() + timedelta(hours=8),
            price=Decimal("100000"),
        )
        # Vé 2: Chiếu sau 1 tiếng -> can_cancel = False (quá hạn 2h)
        st2 = Showtime(
            id=72,
            movie_id=movie.id,
            room_id=room.id,
            start_time=datetime.utcnow() + timedelta(hours=1),
            end_time=datetime.utcnow() + timedelta(hours=3),
            price=Decimal("100000"),
        )
        session.add_all([st1, st2])
        session.flush()

        b1 = Booking(
            id=301,
            booking_code="BK-CAN-CANCEL",
            user_id=user.id,
            showtime_id=st1.id,
            total_price=Decimal("100000"),
            status="DA_THANH_TOAN",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        b2 = Booking(
            id=302,
            booking_code="BK-CANNOT-CANCEL",
            user_id=user.id,
            showtime_id=st2.id,
            total_price=Decimal("100000"),
            status="DA_THANH_TOAN",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add_all([b1, b2])
        session.flush()

        session.add(BookingSeat(booking_id=b1.id, showtime_id=st1.id, seat_id=seat1.id, price=Decimal("100000")))
        session.add(BookingSeat(booking_id=b2.id, showtime_id=st2.id, seat_id=seat2.id, price=Decimal("100000")))
        session.commit()

        tickets = get_user_bookings(user_id=user.id, status_filter=None, db=session)
        assert len(tickets) == 2

        t1 = next(t for t in tickets if t["id"] == 301)
        t2 = next(t for t in tickets if t["id"] == 302)

        assert t1["can_cancel"] is True
        assert t2["can_cancel"] is False
        assert "ít nhất 2 tiếng" in t2["cancel_reason"]
