"""
Unit tests cho API [Vé] Trang "Vé của tôi" (Task T3C5D0B).
"""
import unittest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from app.models.user import User
from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.core.security import create_access_token

class TestMyTicketsApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db = SessionLocal()
        self.user = self.db.query(User).filter(User.email == "customer@cinema.com").first()
        if self.user:
            self.token = create_access_token(data={"sub": str(self.user.id), "email": self.user.email, "role": "USER"})
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.headers = {}

    def tearDown(self):
        self.db.close()

    def test_get_my_tickets_all(self):
        if not self.headers:
            return
        response = self.client.get("/api/bookings/my-tickets", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        if len(data) > 0:
            item = data[0]
            self.assertIn("booking_code", item)
            self.assertIn("status", item)
            self.assertIn("payment_status", item)
            self.assertIn("showtime", item)
            self.assertIn("seats", item)

    def test_get_my_tickets_filter_upcoming(self):
        if not self.headers:
            return
        response = self.client.get("/api/bookings/my-tickets?status_filter=upcoming", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)

    def test_get_my_tickets_filter_cancelled(self):
        if not self.headers:
            return
        response = self.client.get("/api/bookings/my-tickets?status_filter=cancelled", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)

    def test_get_my_tickets_unauthorized(self):
        response = self.client.get("/api/bookings/my-tickets")
        self.assertEqual(response.status_code, 401)

if __name__ == "__main__":
    unittest.main()
