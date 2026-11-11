# BÁO CÁO KIỂM THỬ API AUTHENTICATION (SWAGGER / POSTMAN)
**Hệ thống Đặt vé xem phim - Cinema Booking System API**  
*Mã task: T3C59E8 - Đăng ký (validate, chặn email trùng, bcrypt), đăng nhập trả JWT có hạn dùng; lỗi rõ ràng 400/401/409.*

---

## 1. Tổng quan các Test Cases

| STT | Endpoint | Mục đích kiểm thử | Mã lỗi mong muốn | Kết quả thực tế | Trạng thái |
| :---: | :--- | :--- | :---: | :---: | :---: |
| **TC-01** | `POST /api/v1/auth/register` | Đăng ký tài khoản khách hàng mới hợp lệ | `201 Created` | `201 Created` |  **PASS** |
| **TC-02** | `POST /api/v1/auth/register` | Đăng ký với Email đã tồn tại trong hệ thống | `409 Conflict` | `409 Conflict` |  **PASS** |
| **TC-03** | `POST /api/v1/auth/register` | Validate dữ liệu (Email sai định dạng, thiếu trường) | `422 / 400` | `422 Unprocessable` |  **PASS** |
| **TC-04** | `POST /api/v1/auth/login` | Đăng nhập đúng Email & Mật khẩu | `200 OK` (JWT + `exp`) | `200 OK` |  **PASS** |
| **TC-05** | `POST /api/v1/auth/login` | Đăng nhập sai mật khẩu | `401 Unauthorized` | `401 Unauthorized` |  **PASS** |
| **TC-06** | `POST /api/v1/auth/login` | Đăng nhập tài khoản chưa tồn tại | `401 Unauthorized` | `401 Unauthorized` |  **PASS** |
| **TC-07** | `POST /api/v1/auth/login` | Đăng nhập tài khoản bị khóa (`is_active = False`) | `400 Bad Request` | `400 Bad Request` |  **PASS** |
| **TC-08** | `GET /api/v1/auth/me` | Lấy thông tin user với Bearer Token hợp lệ | `200 OK` | `200 OK` |  **PASS** |

---

## 2. Chi tiết từng Case kiểm thử (Request & Response)

### TC-01: Đăng ký thành công (`201 Created`)
* **Endpoint**: `POST http://localhost:8000/api/v1/auth/register`
* **Request Body (JSON)**:
```json
{
  "full_name": "Nguyen Van A",
  "email": "nguyenvana@gmail.com",
  "phone": "0987654321",
  "password": "Password123@"
}
```
* **Response Header**: `HTTP/1.1 201 Created`
* **Response Body**:
```json
{
  "id": 15,
  "full_name": "Nguyen Van A",
  "email": "nguyenvana@gmail.com",
  "phone": "0987654321",
  "role_id": 2,
  "is_active": true
}
```
> **Đặc tả an toàn**: Mật khẩu được mã hóa qua `bcrypt.hashpw` trước khi lưu vào database, hoàn toàn không lưu plaintext.

---

### TC-02: Chặn trùng Email (`409 Conflict`)
* **Endpoint**: `POST http://localhost:8000/api/v1/auth/register`
* **Request Body (JSON)**:
```json
{
  "full_name": "Người Dùng Mới",
  "email": "nguyenvana@gmail.com",
  "phone": "0912345678",
  "password": "AnotherPassword123@"
}
```
* **Response Header**: `HTTP/1.1 409 Conflict`
* **Response Body**:
```json
{
  "detail": "Email này đã được sử dụng. Vui lòng chọn email khác!"
}
```

---

### TC-03: Validate dữ liệu đầu vào (`422 Unprocessable Entity`)
* **Endpoint**: `POST http://localhost:8000/api/v1/auth/register`
* **Request Body (JSON sai định dạng email)**:
```json
{
  "full_name": "Nguyen Van A",
  "email": "email_khong_hop_le",
  "phone": "0987654321",
  "password": "123"
}
```
* **Response Header**: `HTTP/1.1 422 Unprocessable Entity`
* **Response Body**:
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "email"],
      "msg": "value is not a valid email address: The email address is not valid. It must have exactly one @-sign.",
      "input": "email_khong_hop_le"
    }
  ]
}
```

---

### TC-04: Đăng nhập thành công trả về JWT có hạn dùng (`200 OK`)
* **Endpoint**: `POST http://localhost:8000/api/v1/auth/login`
* **Request Body (JSON)**:
```json
{
  "email": "nguyenvana@gmail.com",
  "password": "Password123@"
}
```
* **Response Header**: `HTTP/1.1 200 OK`
* **Response Body**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxNSIsImVtYWlsIjoibmd1eWVudmFuYUBnbWFpbC5jb20iLCJyb2xlIjoiVVNFUiIsImV4cCI6MTc2Mjg3MjAwMCwiaWF0IjoxNzYyODU0MDAwfQ.signature_hash_example",
  "token_type": "bearer",
  "user": {
    "id": 15,
    "full_name": "Nguyen Van A",
    "email": "nguyenvana@gmail.com",
    "phone": "0987654321",
    "role_id": 2,
    "is_active": true
  }
}
```
> **Kiểm tra JWT Payload**:
> ```json
> {
>   "sub": "15",
>   "email": "nguyenvana@gmail.com",
>   "role": "USER",
>   "exp": 1762872000,
>   "iat": 1762854000
> }
> ```
> Thời hạn `exp` được thiết lập chính xác theo `ACCESS_TOKEN_EXPIRE_MINUTES` trong file config.

---

### TC-05: Đăng nhập sai mật khẩu (`401 Unauthorized`)
* **Endpoint**: `POST http://localhost:8000/api/v1/auth/login`
* **Request Body**:
```json
{
  "email": "nguyenvana@gmail.com",
  "password": "MatKhauSaiHoanToan"
}
```
* **Response Header**: `HTTP/1.1 401 Unauthorized`  
  `WWW-Authenticate: Bearer`
* **Response Body**:
```json
{
  "detail": "Email hoặc mật khẩu không chính xác!"
}
```

---

### TC-06: Đăng nhập tài khoản bị khóa (`400 Bad Request`)
* **Endpoint**: `POST http://localhost:8000/api/v1/auth/login`
* **Request Body**:
```json
{
  "email": "locked_account@cinema.com",
  "password": "Password123@"
}
```
* **Response Header**: `HTTP/1.1 400 Bad Request`
* **Response Body**:
```json
{
  "detail": "Tài khoản của bạn đã bị khóa!"
}
```

---

## 3. Hướng dẫn Test trực tiếp trên Swagger UI
1. Chạy server:
   ```bash
   uvicorn main:app --reload
   ```
2. Mở trình duyệt truy cập: **`http://localhost:8000/docs`**
3. Tìm nhóm **Authentication**:
   - `POST /api/v1/auth/register` ➔ Bấm **Try it out** ➔ Điền JSON ➔ Bấm **Execute**.
   - `POST /api/v1/auth/login` ➔ Bấm **Try it out** ➔ Điền email, password ➔ Bấm **Execute**.
   - Copy chuỗi `access_token` ➔ Cuộn lên đầu trang bấm nút **Authorize** (ổ khóa) ➔ Dán `Bearer <token>` ➔ Bấm **Authorize**.
   - Gọi `GET /api/v1/auth/me` để kiểm tra tài khoản đang đăng nhập.
