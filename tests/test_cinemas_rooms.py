import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from app.models.cinema import Cinema
from app.models.room import Room
from main import app

# In-memory SQLite using StaticPool for consistent session memory
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestCinemasAndRooms(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db = TestingSessionLocal()

        c1 = Cinema(name="CGV Vincom Ba Trieu", address="191 Ba Trieu", city="Ha Noi", phone="19006017")
        c2 = Cinema(name="CGV Landmark 81", address="720A Dien Bien Phu", city="TP. Ho Chi Minh", phone="19006018")
        db.add_all([c1, c2])
        db.commit()
        db.refresh(c1)
        db.refresh(c2)
        self.c1_id = c1.id
        self.c2_id = c2.id

        r1 = Room(cinema_id=c1.id, name="Cinema 01", room_type="2D", total_seats=60)
        r2 = Room(cinema_id=c1.id, name="Cinema 02", room_type="IMAX", total_seats=96)
        r3 = Room(cinema_id=c2.id, name="Room 01", room_type="3D", total_seats=80)
        db.add_all([r1, r2, r3])
        db.commit()
        db.refresh(r1)
        self.r1_id = r1.id
        db.close()

    def tearDown(self):
        Base.metadata.drop_all(bind=engine)

    def test_get_all_cinemas(self):
        response = client.get("/api/cinemas")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        names = [c["name"] for c in data]
        self.assertIn("CGV Vincom Ba Trieu", names)
        self.assertIn("CGV Landmark 81", names)

    def test_filter_cinemas_by_city(self):
        response = client.get("/api/cinemas?city=Ha Noi")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["city"], "Ha Noi")

    def test_get_cinema_detail_with_rooms(self):
        response = client.get(f"/api/cinemas/{self.c1_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "CGV Vincom Ba Trieu")
        self.assertEqual(len(data["rooms"]), 2)

    def test_get_cinema_rooms_endpoint(self):
        response = client.get(f"/api/cinemas/{self.c1_id}/rooms")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        room_names = [r["name"] for r in data]
        self.assertIn("Cinema 01", room_names)
        self.assertIn("Cinema 02", room_names)

    def test_get_cinema_not_found(self):
        response = client.get("/api/cinemas/99999")
        self.assertEqual(response.status_code, 404)

    def test_get_all_rooms(self):
        response = client.get("/api/rooms")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 3)

    def test_filter_rooms_by_cinema_and_type(self):
        response = client.get(f"/api/rooms?cinema_id={self.c1_id}&room_type=IMAX")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Cinema 02")
        self.assertEqual(data[0]["room_type"], "IMAX")

    def test_get_room_detail(self):
        response = client.get(f"/api/rooms/{self.r1_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Cinema 01")
        self.assertEqual(data["total_seats"], 60)

    def test_get_room_not_found(self):
        response = client.get("/api/rooms/99999")
        self.assertEqual(response.status_code, 404)

    def test_create_and_delete_cinema(self):
        new_cinema_payload = {
            "name": "Lotte Cinema Landmark",
            "address": "Pham Hung",
            "city": "Ha Noi",
            "phone": "02438378032"
        }
        res_create = client.post("/api/cinemas", json=new_cinema_payload)
        self.assertEqual(res_create.status_code, 201)
        created_id = res_create.json()["id"]

        # Duplicate name should fail 409
        res_dup = client.post("/api/cinemas", json=new_cinema_payload)
        self.assertEqual(res_dup.status_code, 409)

        # Delete
        res_del = client.delete(f"/api/cinemas/{created_id}")
        self.assertEqual(res_del.status_code, 204)
