"""
Unit tests cho tính năng Xem, sửa hồ sơ cá nhân và đổi mật khẩu (Task T3C5C51).
"""
import unittest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from app.models.user import User
from app.core.security import create_access_token

class TestUsersProfile(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db = SessionLocal()
        # Tìm user mẫu
        self.user = self.db.query(User).filter(User.email == "customer@cinema.com").first()
        if self.user:
            self.token = create_access_token(data={"sub": str(self.user.id), "email": self.user.email, "role": "USER"})
        else:
            self.token = ""

    def tearDown(self):
        self.db.close()

    def test_get_profile(self):
        if not self.token:
            return
        response = self.client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("email", data)
        self.assertIn("full_name", data)

    def test_update_profile(self):
        if not self.token:
            return
        payload = {
            "full_name": "Nguyen Van Khach Hang Updated",
            "phone": "0987654321"
        }
        response = self.client.put(
            "/api/v1/users/me",
            json=payload,
            headers={"Authorization": f"Bearer {self.token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["full_name"], "Nguyen Van Khach Hang Updated")

    def test_change_password_wrong_old_password(self):
        if not self.token:
            return
        payload = {
            "old_password": "wrongpassword123",
            "new_password": "newpassword123"
        }
        response = self.client.post(
            "/api/v1/users/change-password",
            json=payload,
            headers={"Authorization": f"Bearer {self.token}"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mật khẩu hiện tại không chính xác", response.json()["detail"])

    def test_change_password_same_as_old(self):
        if not self.token:
            return
        payload = {
            "old_password": "user123",
            "new_password": "user123"
        }
        response = self.client.post(
            "/api/v1/users/change-password",
            json=payload,
            headers={"Authorization": f"Bearer {self.token}"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("không được trùng", response.json()["detail"])

if __name__ == "__main__":
    unittest.main()
