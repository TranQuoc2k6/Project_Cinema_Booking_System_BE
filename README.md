# Project Cinema Booking System - Backend (FastAPI)

Hệ thống đặt vé xem phim trực tuyến — Phân hệ Backend API xây dựng bằng **FastAPI**, **SQLAlchemy** và **MySQL/SQLite**.

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Dữ Liệu Mẫu (Seed Data)

### 1. Cài đặt môi trường ảo & Thư viện
```bash
# Kích hoạt môi trường ảo (nếu dùng Windows)
.\venv\Scripts\activate

# Cài đặt các gói phụ thuộc
pip install -r requirements.txt
```

### 2. Cấu hình Cơ sở dữ liệu
Sao chép file `.env.example` thành `.env` và điều chỉnh thông tin kết nối MySQL:
```bash
cp .env.example .env
```
*(Nếu MySQL máy bạn có mật khẩu khác, chỉnh lại `DATABASE_URL` trong file `.env`)*

### 3. Khởi tạo Bảng & Nạp Dữ Liệu Mẫu 7 Ngày (Seed Data)
Chạy script tự động khởi tạo và seed dữ liệu mẫu:
```bash
python seed_data.py
# hoặc
python init_db.py
```
> **Hoặc nếu muốn import trực tiếp qua MySQL Workbench / phpMyAdmin:**  
> Mở và chạy file `seed_data.sql` (hoặc `docs/seed_data.sql`).

---

## 👥 Danh Sách Tài Khoản Mẫu Cho Cả Nhóm Test

| Vai trò | Email đăng nhập | Mật khẩu | Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| **Quản trị viên (Admin)** | `admin@cinema.com` | `admin123` | Quản trị phim, suất chiếu, phòng, rạp, đơn vé, thống kê |
| **Admin Quản lý** | `hung.le@cinema.com` | `admin123` | Tài khoản Admin kiểm thử phân quyền quản lý |
| **Khách hàng 1 (Customer)** | `customer@cinema.com` | `user123` | Đặt vé, chọn ghế, thanh toán đơn vé mẫu |
| **Khách hàng 2 (Customer)** | `lan.tran@cinema.com` | `user123` | Kiểm thử tài khoản khách hàng thông thường |

---

## 🎬 Dữ Liệu Mẫu Được Sinh Ra
- **4 Cụm rạp lớn**: CGV Vincom Bà Triệu, CGV Landmark 81, Lotte Cinema Keangnam, Galaxy Cinema Nguyễn Du.
- **9 Phòng chiếu hiện đại**: Đầy đủ các định dạng 2D Standard, 3D RealD, IMAX with Laser, VIP Gold Class.
- **584 Ghế ngồi**: Đầy đủ các phân loại ghế `STANDARD`, `VIP`, `COUPLE` (Ghế đôi Sweetbox).
- **7 Phim bom tấn**: Mai, Lật Mặt 7, Dune 2, Exhuma (Quật Mộ Trùng Ma), Godzilla x Kong, Kung Fu Panda 4, Conan.
- **161 Suất chiếu cho 7 ngày liên tiếp**: Phân bổ linh hoạt từ 09:00 sáng đến 23:30 đêm, giá vé từ 75,000đ - 165,000đ theo từng định dạng phòng chiếu.

---

## 🌐 Chạy Máy Chủ API
```bash
uvicorn main:app --reload --port 8000
```
Tài liệu Swagger UI tự động: `http://localhost:8000/docs`
