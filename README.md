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

### Lấy suất chiếu theo phim, rạp và ngày
`GET /api/showtimes` hỗ trợ các bộ lọc tùy chọn `movieId`, `cinemaId` và `date` (`YYYY-MM-DD`). Kết quả chỉ gồm suất chiếu chưa bắt đầu và được nhóm theo rạp:

```text
/api/showtimes?movieId=1&cinemaId=2&date=2026-11-13
```

Mỗi nhóm chứa thông tin rạp và danh sách suất chiếu, gồm phim, phòng, thời gian và giá vé. Khi không truyền bộ lọc, API trả về tất cả suất chiếu sắp tới.

### Tạo sơ đồ ghế cho phòng chiếu
Gửi `POST /api/rooms/{room_id}/seats/generate` với số hàng/cột và số hàng VIP/ghế đôi ở cuối sơ đồ:
```json
{
  "rows": 8,
  "columns": 12,
  "vip_rows": 2,
  "couple_rows": 1
}
```
Các hàng thường nằm phía trước, tiếp theo là hàng VIP, cuối cùng là hàng ghế đôi. Mỗi cột trong hàng đôi vẫn được tạo thành một ghế `couple`. Sơ đồ có giới hạn 2.000 ghế; API không ghi đè phòng đã có ghế và đồng thời cập nhật `total_seats` của phòng.


## Lấy lại mật khẩu cho khách hàng

```bash
cd /Users/mac/Documents/Cinema_Booking_System/Project_Cinema_Booking_System_BE

venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from database import SessionLocal
from app.models.user import User
from app.core.security import hash_password

db = SessionLocal()
target_email = 'hay123@gmail.com'
new_pass = '123456'

user = db.query(User).filter(User.email == target_email).first()
if user:
    user.password_hash = hash_password(new_pass)
    db.commit()
    print(f'-> Đã đổi mật khẩu tài khoản {target_email} thành: {new_pass}')
else:
    print('Không tìm thấy tài khoản.')
db.close()
"
```


---

## 📁 Cấu Trúc Thư Mục

```text
Project_Cinema_Booking_System_BE/
├── main.py                                  # Entry point FastAPI, CORS, lifespan, đăng ký router & /uploads
├── database.py                              # Kết nối SQLAlchemy (engine, SessionLocal, Base, get_db)
├── init_db.py                               # Khởi tạo bảng & nạp dữ liệu mẫu
├── seed_data.py                             # Script Python sinh dữ liệu mẫu (admin, user, rạp, phòng, ghế, phim, lịch chiếu)
├── seed_data.sql                            # File SQL dữ liệu mẫu
├── test_seed_result.py                      # Script kiểm tra kết quả sau khi seed
├── requirements.txt                         # Danh sách thư viện Python phụ thuộc
├── pytest.ini                               # Cấu hình Pytest
├── .env                                     # Biến môi trường (DATABASE_URL, SECRET_KEY,...)
├── README.md                                # Tài liệu hướng dẫn cài đặt & chạy Backend
├── docs/
│   ├── ERD_Cinema_Booking_System.png        # Ảnh sơ đồ ERD cơ sở dữ liệu
│   └── ERD_drawio.xml                       # File nguồn sơ đồ ERD (Draw.io)
├── migrations/                              # Thư mục migrations (hiện chỉ có .gitkeep)
├── app/
│   ├── __init__.py
│   ├── core/                                # Cấu hình lõi, bảo mật & tính giá
│   │   ├── config.py                        # Đọc biến môi trường (DB, JWT SECRET_KEY, ALGORITHM, EXPIRE)
│   │   ├── dependencies.py                  # Dependency xác thực JWT (get_current_user, require_admin)
│   │   ├── pricing.py                       # Engine tính giá vé theo loại ghế, cuối tuần, giờ vàng
│   │   ├── pricing_config.json              # Cấu hình hệ số/phụ thu giá vé
│   │   └── security.py                      # Hash/verify mật khẩu (Bcrypt/SHA-256) & tạo JWT token
│   ├── models/                              # SQLAlchemy ORM Models (bảng DB)
│   │   ├── __init__.py
│   │   ├── role.py                          # Vai trò (ADMIN / USER)
│   │   ├── user.py                          # Người dùng / Khách hàng
│   │   ├── genre.py                         # Thể loại phim & bảng liên kết movie_genres
│   │   ├── movie.py                         # Phim
│   │   ├── movie_genre.py                   # Bảng trung gian movie_genres
│   │   ├── cinema.py                        # Cụm rạp
│   │   ├── room.py                          # Phòng chiếu
│   │   ├── seat.py                          # Ghế ngồi (standard / vip / couple)
│   │   ├── showtime.py                      # Suất chiếu
│   │   ├── booking.py                       # Đơn đặt vé (GIU_CHO / DA_THANH_TOAN / DA_HUY / HET_HAN)
│   │   ├── booking_seat.py                  # Ghế thuộc đơn đặt vé (chống đặt trùng suất)
│   │   ├── booking_combo.py                 # Combo bắp nước kèm đơn vé
│   │   ├── combo.py                         # Danh mục combo bắp nước
│   │   ├── payment.py                       # Giao dịch thanh toán
│   │   ├── review.py                        # Đánh giá & bình luận phim
│   │   └── ticket.py                        # (File trống 0B - placeholder)
│   ├── schemas/                             # Pydantic Schemas (validate request/response)
│   │   ├── auth.py, booking.py, cinema.py, combo.py, genre.py, movie.py,
│   │   │   payment.py, review.py, room.py, seat.py, showtime.py, user.py
│   │   └── ticket.py                        # (File trống 0B - placeholder)
│   ├── routers/                             # FastAPI Endpoints
│   │   ├── auth.py                          # /api/v1/auth (đăng ký, đăng nhập, /me, /admin-check)
│   │   ├── movies.py                        # API phim công khai & upload poster
│   │   ├── cinemas.py, rooms.py, seats.py   # API rạp, phòng chiếu & cấu hình sơ đồ ghế
│   │   ├── showtimes.py                     # API lịch chiếu & sơ đồ ghế theo suất
│   │   ├── combos.py                        # API combo bắp nước cho khách
│   │   ├── bookings.py                      # API giữ ghế (/hold), xác nhận, vé của tôi
│   │   ├── tickets.py                       # API vé điện tử, tra cứu QR, soát vé, hủy vé
│   │   ├── payments.py                      # API phương thức & thanh toán sandbox
│   │   ├── reviews.py                       # API đánh giá phim & kiểm tra điều kiện đánh giá
│   │   ├── users.py                         # API hồ sơ cá nhân & đổi mật khẩu
│   │   ├── genres.py                        # (File trống 0B - placeholder)
│   │   └── admin/                           # Nhóm API Quản trị (/api/admin/...)
│   │       ├── __init__.py                  # Gom router admin & gắn require_admin
│   │       ├── dashboard.py                 # Thống kê KPI, doanh thu, tỷ lệ lấp đầy
│   │       ├── movies.py                    # CRUD phim, đổi trạng thái, upload poster
│   │       ├── showtimes.py                 # CRUD suất chiếu, auto-generate, cleanup
│   │       ├── bookings.py                  # Quản lý & hủy đơn vé
│   │       ├── combos.py                    # CRUD combo bắp nước
│   │       └── users.py                     # Quản lý khách hàng & khóa/mở tài khoản
│   ├── services/                            # Tầng xử lý nghiệp vụ
│   │   ├── __init__.py
│   │   ├── auth_service.py, booking_service.py, combo_service.py,
│   │   │   dashboard_service.py, movie_service.py, review_service.py,
│   │   │   seat_service.py, showtime_service.py, user_service.py
│   │   ├── payment_service.py               # (File trống 0B - placeholder)
│   │   └── ticket_service.py                # (File trống 0B - placeholder)
│   ├── uploads/                             # Thư mục tĩnh lưu file upload (/uploads)
│   │   ├── avatars/                         # (Hiện chỉ có .gitkeep)
│   │   └── posters/                         # (Hiện chỉ có .gitkeep)
│   └── utils/                               # (3 file trống 0B: helpers.py, response.py, validators.py)
└── tests/                                   # 20 file Pytest kiểm thử Backend
    ├── test_auth.py, test_users_profile.py
    ├── test_movies.py, test_admin_movies.py, test_movie_reviews.py, test_movie_reviews_direct.py
    ├── test_cinemas_rooms.py, test_seats.py, test_seat_pricing_and_surcharges.py
    ├── test_showtimes.py, test_showtime_listing.py, test_admin_showtimes.py
    ├── test_combos.py, test_booking_hold.py, test_bookings.py
    ├── test_confirm_booking_and_auto_expire.py, test_payment_sandbox.py
    └── test_my_tickets_api.py, test_electronic_ticket_and_cancel.py, test_qr_ticket_verification.py
```
