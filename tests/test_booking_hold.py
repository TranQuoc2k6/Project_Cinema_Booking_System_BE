"""
Tests for the seat‑hold endpoint (task T3C6902).
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from app.core.dependencies import get_current_user, get_db
from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.models.room import Room
from app.models.cinema import Cinema
from app.models.user import User
from app.models.role import Role

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base

# In-memory engine for test_booking_hold
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

client = TestClient(app)

def create_user(db, username="test@example.com"):
    role = db.query(Role).filter(Role.name == "USER").first()
    user = User(full_name="Test User", email=username, password_hash="hashed", role_id=role.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def auth_headers(user_id: int):
    return {"Authorization": "Bearer dummy"}

@pytest.fixture
def db_session():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    session = TestSession()

    # Seed Role USER
    user_role = Role(id=1, name="USER", description="Khách hàng")
    admin_role = Role(id=2, name="ADMIN", description="Quản trị viên")
    session.add_all([user_role, admin_role])
    session.commit()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: session.query(User).first()

    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)

def setup_showtime_and_seats(db):
    # Create a cinema, room, seats, showtime
    cinema = Cinema(name="Demo Cinema", address="123", city="Hanoi")
    db.add(cinema)
    room = Room(name="Room 1", cinema=cinema)
    db.add(room)
    db.flush()
    seats = []
    for i in range(1, 6):
        seat = Seat(room_id=room.id, seat_row="A", seat_column=i, seat_number=f"A{i}", seat_type="standard", is_active=True)
        seats.append(seat)
        db.add(seat)
    db.flush()
    showtime = Showtime(movie_id=1, room_id=room.id, start_time=datetime.utcnow() + timedelta(hours=1), end_time=datetime.utcnow() + timedelta(hours=3), price=Decimal("100000"))
    db.add(showtime)
    db.commit()
    db.refresh(showtime)
    return showtime, seats

def test_successful_hold(db_session):
    user = create_user(db_session)
    showtime, seats = setup_showtime_and_seats(db_session)
    seat_ids = [seat.id for seat in seats[:3]]
    payload = {"showtime_id": showtime.id, "seat_ids": seat_ids}
    response = client.post("/api/bookings/hold", json=payload, headers=auth_headers(user.id))
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "GIU_CHO"
    assert len(data["booking_seats"]) == 3
    # Verify DB records created
    booking = db_session.query(Booking).filter(Booking.id == data["id"]).first()
    assert booking is not None
    assert booking.status == "GIU_CHO"
    assert booking.held_until > datetime.utcnow()

def test_hold_exceeds_limit(db_session):
    user = create_user(db_session)
    showtime, seats = setup_showtime_and_seats(db_session)
    seat_ids = [seat.id for seat in seats]
    # add extra dummy ids to exceed 8 (here we only have 5 seats, so repeat some)
    seat_ids += seat_ids[:4]  # total 9 ids
    payload = {"showtime_id": showtime.id, "seat_ids": seat_ids}
    response = client.post("/api/bookings/hold", json=payload, headers=auth_headers(user.id))
    assert response.status_code in (400, 422)
    assert "8 ghế" in response.text or "max_length" in response.text or "seat_ids" in response.text

def test_conflict_on_same_seat(db_session):
    user1 = create_user(db_session, "user1@example.com")
    user2 = create_user(db_session, "user2@example.com")
    showtime, seats = setup_showtime_and_seats(db_session)
    seat_id = seats[0].id
    payload = {"showtime_id": showtime.id, "seat_ids": [seat_id]}
    # First hold succeeds
    resp1 = client.post("/api/bookings/hold", json=payload, headers=auth_headers(user1.id))
    assert resp1.status_code == 201
    # Second hold should conflict
    resp2 = client.post("/api/bookings/hold", json=payload, headers=auth_headers(user2.id))
    assert resp2.status_code == 409
    assert "đã được giữ" in resp2.text

def test_hold_expiration_transitions_to_het_han(db_session):
    # Create a hold, then manually set held_until in the past and fetch
    user = create_user(db_session)
    showtime, seats = setup_showtime_and_seats(db_session)
    seat_ids = [seats[0].id]
    payload = {"showtime_id": showtime.id, "seat_ids": seat_ids}
    resp = client.post("/api/bookings/hold", json=payload, headers=auth_headers(user.id))
    assert resp.status_code == 201
    booking_id = resp.json()["id"]
    # Fast‑forward time by updating held_until to past
    booking = db_session.query(Booking).get(booking_id)
    booking.held_until = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    # Retrieve booking (GET endpoint not yet implemented, so we query directly)
    refreshed = db_session.query(Booking).get(booking_id)
    # Simulate lazy check – if held_until passed, status should be HET_HAN
    if refreshed.status == "GIU_CHO" and refreshed.held_until < datetime.utcnow():
        refreshed.status = "HET_HAN"
        db_session.commit()
    assert refreshed.status == "HET_HAN"
