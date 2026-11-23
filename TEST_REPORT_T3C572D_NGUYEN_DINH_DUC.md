# BÁO CÁO KIỂM THỬ PHẦN MỀM (TEST PLAN, TEST CASES & TEST LOG)
## PHÂN HỆ: ĐẶT VÉ VÀ THANH TOÁN (BOOKING & PAYMENT MODULE)

- **Dự án**: Cinema Booking System
- **Học viên**: **Nguyễn Đình Đức**
- **Mã sinh viên**: **B25DTCN158**
- **Sprint**: Sprint 3 (12/11/2026 - 23/11/2026)
- **Mã Task LMS Rikkei**: **T3C572D**
- **Tiêu đề task**: `[Kiểm thử] Test case và test log module mình`
- **File Excel đính kèm**: `Test_Case_va_Test_Log_T3C572D_NguyenDinhDuc.xlsx`

---

## I. TỔNG QUAN & THỐNG KÊ KẾT QUẢ KIỂM THỬ

### 1. Chỉ số kiểm thử (Test Metrics)
| Tổng số Test Cases | Số Test Đạt (PASS) | Số Test Thất Bại (FAIL) | Tỷ lệ Đạt (%) | Bug phát hiện | Bug đã sửa |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **35** | **35** | **0** | **100%** | **5** | **5 (100%)** |

### 2. Phân bổ theo 4 tiêu chí bắt buộc theo yêu cầu đề bài
| Tiêu chí kiểm thử | Số Test Cases | Tỷ lệ (%) | Mục tiêu kiểm thử | Trạng thái |
| :--- | :---: | :---: | :--- | :---: |
| **1. Đúng dữ liệu (Positive/Valid)** | 15 | 42.9% | Luồng hoạt động chính xác (Happy path) của toàn bộ 5 chức năng | **15/15 PASS** |
| **2. Sai dữ liệu (Negative/Boundary)** | 10 | 28.6% | Xác thực dữ liệu đầu vào, biên số lượng ghế (> 8 ghế), ghế trùng, quá hạn | **10/10 PASS** |
| **3. Chưa đăng nhập (Authentication)** | 5 | 14.3% | Chặn truy cập khi thiếu Bearer Token (HTTP 401 Unauthorized) | **5/5 PASS** |
| **4. Sai quyền / Trái phép (Authorization)** | 5 | 14.3% | Ngăn chặn truy cập chéo đơn hàng của tài khoản khác (HTTP 403 Forbidden / IDOR) | **5/5 PASS** |
| **TỔNG CỘNG** | **35** | **100%** | Bao phủ 100% các chức năng đảm nhiệm | **35/35 PASS** |

### 3. Danh sách các chức năng / Sub-tasks do học viên Nguyễn Đình Đức phụ trách
1. **T3C68E8 & T3C6AF7**: Sơ đồ ghế, trạng thái ghế (Trống/Giữ/Đã đặt) và tính giá theo loại ghế (Standard, VIP, Couple).
2. **T3C6902 & T3C6AF7**: API Giữ ghế 10 phút (tối đa 8 ghế), transaction chống trùng ghế, đếm ngược đồng hồ frontend.
3. **T3C6CE6**: API Xác nhận đặt vé từ ghế đang giữ, tính lại tiền độc lập trên server, tự động chuyển giữ chỗ quá hạn sang HET_HAN để trả ghế.
4. **T3C6D00**: Thanh toán mô phỏng Sandbox (MoMo, VNPAY, ZaloPay, Thẻ quốc tế), cập nhật trạng thái vé DA_THANH_TOAN hoặc giữ GIU_CHO khi thất bại.
5. **T3C6D1A**: Xem danh sách vé điện tử kèm mã QR Code và chức năng Hủy vé trước giờ chiếu 2 tiếng để hoàn trả ghế.

---

## II. DANH SÁCH CHI TIẾT 35 TEST CASES

### Nhóm 1: Sơ đồ ghế & Tính giá vé (Task T3C68E8 & T3C6AF7)
- **TC_SEAT_01 [Đúng dữ liệu]**: Lấy danh sách sơ đồ ghế của suất chiếu hợp lệ (`GET /api/showtimes/1/seats`). Mong đợi: HTTP 200, trả về đủ danh sách hàng ghế (A, B, C...), các loại ghế (standard, vip, couple), giá tương ứng và trạng thái (TRONG/GIU_CHO/DA_DAT). -> **PASS**
- **TC_SEAT_02 [Sai dữ liệu]**: Gọi API với suất chiếu không tồn tại (`GET /api/showtimes/999999/seats`). Mong đợi: HTTP 404 Not Found, detail "Suất chiếu không tồn tại". -> **PASS**
- **TC_SEAT_03 [Sai dữ liệu]**: Gọi API với ID không hợp lệ (`GET /api/showtimes/-5/seats`). Mong đợi: HTTP 422 Unprocessable Entity. -> **PASS**
- **TC_SEAT_04 [Đúng dữ liệu - UI]**: Người dùng click chọn ghế Standard (100k), VIP (150k), Couple (200k). Mong đợi: Ghế đổi màu sang xanh dương, tổng tiền tạm tính hiển thị chính xác 450,000 VNĐ. -> **PASS**
- **TC_SEAT_05 [Sai dữ liệu - Boundary UI]**: Người dùng click chọn liên tiếp quá 8 ghế. Mong đợi: Hệ thống hiển thị alert chặn không cho chọn ghế thứ 9 ("Chỉ được chọn tối đa 8 ghế"). -> **PASS**
- **TC_SEAT_06 [Sai dữ liệu - UI Logic]**: Người dùng click vào ghế đã bán (màu đỏ) hoặc đang giữ (màu vàng). Mong đợi: Ghế bị disabled, con trỏ dạng not-allowed, không làm thay đổi tổng tiền. -> **PASS**

### Nhóm 2: Giữ ghế 10 phút (Task T3C6902 & T3C6AF7)
- **TC_HOLD_07 [Đúng dữ liệu]**: User đã đăng nhập gửi request giữ 2 ghế trống (`POST /api/bookings/hold`). Mong đợi: HTTP 201 Created, booking.status = 'GIU_CHO', held_until = now + 10 phút, tạo 2 bản ghi booking_seats. -> **PASS**
- **TC_HOLD_08 [Sai dữ liệu]**: Gửi request với mảng seat_ids rỗng `[]`. Mong đợi: HTTP 422 Unprocessable Entity báo lỗi phải chọn ít nhất 1 ghế. -> **PASS**
- **TC_HOLD_09 [Sai dữ liệu - Boundary]**: Gửi request qua API với 9 ghế (vượt max limit 8). Mong đợi: HTTP 400 Bad Request ("Không được chọn quá 8 ghế trong một lần"). -> **PASS**
- **TC_HOLD_10 [Sai dữ liệu]**: Gửi seat_id không tồn tại trong CSDL. Mong đợi: HTTP 400 Bad Request ("Một hoặc nhiều seat_id không tồn tại"). -> **PASS**
- **TC_HOLD_11 [Sai dữ liệu]**: Gửi seat_id thuộc phòng chiếu khác phòng của suất chiếu. Mong đợi: HTTP 400 Bad Request ("Ghế không thuộc cùng phòng với suất chiếu"). -> **PASS**
- **TC_HOLD_12 [Sai dữ liệu - Concurrency]**: 2 người dùng cùng giữ 1 ghế tại cùng thời điểm. Mong đợi: User 1 nhận HTTP 201 Created, User 2 nhận HTTP 409 Conflict ("Một hoặc nhiều ghế đã được giữ hoặc đã đặt"). -> **PASS**
- **TC_HOLD_13 [Chưa đăng nhập]**: Gọi API giữ ghế không có Bearer token. Mong đợi: HTTP 401 Unauthorized ("Chưa đăng nhập hoặc thiếu token"). -> **PASS**
- **TC_HOLD_14 [Đúng dữ liệu - UI Timer]**: Đồng hồ đếm lùi 10:00 trên giao diện thanh toán. Mong đợi: Đếm lùi chính xác từng giây (09:59 -> 09:58...). -> **PASS**
- **TC_HOLD_15 [Đúng dữ liệu - Tự động hết hạn]**: Khi đơn quá 10 phút mà chưa thanh toán. Mong đợi: Status chuyển 'HET_HAN', xóa BookingSeat giải phóng ghế về trạng thái trống. -> **PASS**

### Nhóm 3: Xác nhận đặt vé & Tính lại tiền Server (Task T3C6CE6)
- **TC_CONFIRM_16 [Đúng dữ liệu]**: Xác nhận đơn booking hợp lệ đang ở trạng thái 'GIU_CHO'. Mong đợi: HTTP 200, status chuyển PENDING, server tính lại tổng tiền từ DB (bỏ qua giá client gửi). -> **PASS**
- **TC_CONFIRM_17 [Sai dữ liệu]**: Xác nhận lại đơn booking đã chuyển sang 'DA_THANH_TOAN'. Mong đợi: HTTP 400 Bad Request. -> **PASS**
- **TC_CONFIRM_18 [Sai dữ liệu]**: Xác nhận đơn booking đã quá hạn 10 phút. Mong đợi: HTTP 400 Bad Request ("Đơn giữ chỗ đã hết hạn"), tự động nhả ghế. -> **PASS**
- **TC_CONFIRM_19 [Chưa đăng nhập]**: Gọi API xác nhận không kèm header Authorization. Mong đợi: HTTP 401 Unauthorized. -> **PASS**
- **TC_CONFIRM_20 [Sai quyền / IDOR]**: User A cố tình gửi request xác nhận đơn booking thuộc về User B. Mong đợi: HTTP 403 Forbidden ("Bạn không có quyền thao tác trên đơn hàng này"). -> **PASS**

### Nhóm 4: Thanh toán mô phỏng Sandbox (Task T3C6D00)
- **TC_PAY_21 [Đúng dữ liệu]**: Lấy danh sách phương thức thanh toán (`GET /api/payments/methods`). Mong đợi: HTTP 200 trả về 4 cổng: VNPAY, MOMO, ZALOPAY, CREDIT_CARD. -> **PASS**
- **TC_PAY_22 [Đúng dữ liệu]**: Mô phỏng thanh toán thành công (`simulate_status = SUCCESS`). Mong đợi: HTTP 200, tạo giao dịch thanh toán thành công, cập nhật booking sang 'DA_THANH_TOAN', sinh mã vé. -> **PASS**
- **TC_PAY_23 [Đúng dữ liệu]**: Mô phỏng thanh toán thất bại (`simulate_status = FAILED`). Mong đợi: HTTP 200, ghi nhận Payment FAILED, booking giữ nguyên trạng thái 'GIU_CHO' để khách thử lại phương thức khác. -> **PASS**
- **TC_PAY_24 [Sai dữ liệu]**: Thanh toán đơn hàng khi thời gian giữ chỗ đã hết hạn. Mong đợi: HTTP 400 Bad Request ("Đơn đặt vé đã hết hạn giữ chỗ"). -> **PASS**
- **TC_PAY_25 [Sai dữ liệu]**: Gửi phương thức thanh toán không tồn tại (vd: 'BITCOIN'). Mong đợi: HTTP 422 Unprocessable Entity. -> **PASS**
- **TC_PAY_26 [Chưa đăng nhập]**: Gọi API thanh toán không có token. Mong đợi: HTTP 401 Unauthorized. -> **PASS**
- **TC_PAY_27 [Sai quyền / IDOR]**: User A gửi thanh toán cho đơn hàng của User B. Mong đợi: HTTP 403 Forbidden ("Bạn không có quyền thực hiện giao dịch cho đơn hàng này"). -> **PASS**

### Nhóm 5: Vé điện tử & Hủy vé trước 2 tiếng (Task T3C6D1A)
- **TC_TICKET_28 [Đúng dữ liệu]**: Xem danh sách "Vé của tôi" (`GET /api/bookings/my-tickets`). Mong đợi: HTTP 200, hiển thị đầy đủ thông tin vé, rạp, phòng, ghế, suất chiếu, cờ can_cancel. -> **PASS**
- **TC_TICKET_29 [Đúng dữ liệu]**: Xem chi tiết 1 vé điện tử. Mong đợi: HTTP 200, modal hiển thị mã QR Code điện tử rõ nét phục vụ soát vé. -> **PASS**
- **TC_TICKET_30 [Đúng dữ liệu]**: Khách hủy vé khi suất chiếu cách hiện tại > 2 tiếng. Mong đợi: HTTP 200, booking sang 'DA_HUY', giải phóng BookingSeat để trả ghế về sơ đồ cho người khác đặt. -> **PASS**
- **TC_TICKET_31 [Sai dữ liệu - Nghiệp vụ]**: Khách hủy vé khi suất chiếu cách hiện tại < 2 tiếng. Mong đợi: HTTP 400 Bad Request ("Không thể huỷ vé trước giờ chiếu dưới 2 tiếng"). -> **PASS**
- **TC_TICKET_32 [Sai dữ liệu - Nghiệp vụ]**: Khách hủy vé của suất chiếu đã diễn ra trong quá khứ. Mong đợi: HTTP 400 Bad Request ("Không thể huỷ vé của suất chiếu đã diễn ra"). -> **PASS**
- **TC_TICKET_33 [Sai dữ liệu]**: Khách gửi request hủy một vé đã bị hủy trước đó. Mong đợi: HTTP 400 Bad Request ("Đơn đặt vé này đã được huỷ trước đó"). -> **PASS**
- **TC_TICKET_34 [Chưa đăng nhập]**: Gọi API xem vé hoặc hủy vé không có token. Mong đợi: HTTP 401 Unauthorized. -> **PASS**
- **TC_TICKET_35 [Sai quyền / IDOR]**: User A gửi request hủy vé của User B. Mong đợi: HTTP 403 Forbidden ("Bạn không có quyền huỷ đơn đặt vé này"). -> **PASS**

---

## III. BÁO CÁO 5 BUG THỰC TẾ ĐÃ PHÁT HIỆN VÀ SỬA CHỮA

| Mã Bug | Chức năng | Mô tả lỗi phát hiện | Mức độ | Nguyên nhân gốc rễ | Giải pháp đã sửa | File đã sửa | Trạng thái |
| :--- | :--- | :--- | :---: | :--- | :--- | :--- | :---: |
| **BUG-01** | Giữ ghế (Seat Hold) | 2 người dùng cùng chọn 1 ghế và nhấn giữ ghế đồng thời dẫn tới race-condition trùng ghế | Nghiêm trọng | Thiếu ràng buộc `UNIQUE` trên cặp `(showtime_id, seat_id)` trong bảng `booking_seats` | Bổ sung `UniqueConstraint("showtime_id", "seat_id", name="uq_showtime_seat")` và bắt `IntegrityError` trả về 409 Conflict | `app/models/booking_seat.py`<br>`app/services/booking_service.py` | **ĐÃ SỬA (PASS)** |
| **BUG-02** | Xác nhận đặt vé | Người dùng sửa tham số `total_price` ở DevTools Console gửi lên API confirm booking khiến mua vé sai giá | Nghiêm trọng | Backend tin cậy giá tiền do frontend gửi lên trong request body | Viết hàm `recalculate_booking_price` tính lại toàn bộ tiền độc lập trên server dựa vào DB | `app/services/booking_service.py`<br>`app/routers/bookings.py` | **ĐÃ SỬA (PASS)** |
| **BUG-03** | Hủy vé trước 2h | Khách hủy vé trước 3h thực tế vẫn bị báo lỗi quá hạn hủy dưới 2 tiếng | Trung bình | Lệch múi giờ giữa máy chủ (UTC) và giờ Việt Nam (GMT+7) khi so sánh `datetime.now()` | Chuẩn hóa toàn bộ thời gian về `datetime.utcnow()` đồng nhất trên toàn hệ thống | `app/services/booking_service.py` | **ĐÃ SỬA (PASS)** |
| **BUG-04** | Nhả ghế hết hạn & Hủy vé | Trạng thái booking đã chuyển `DA_HUY` / `HET_HAN` nhưng ghế trên sơ đồ vẫn bị khóa đỏ | Cao | Bản ghi trong bảng `booking_seats` vẫn tồn tại khiến query sơ đồ ghế coi ghế vẫn bận | Bổ sung logic xóa các bản ghi `BookingSeat` tương ứng khi hủy vé hoặc khi hết hạn giữ chỗ | `app/services/booking_service.py` | **ĐÃ SỬA (PASS)** |
| **BUG-05** | Giao diện Frontend | Khách chưa đăng nhập bấm vào "Vé của tôi" hoặc "Đặt vé" thì giao diện bị crash trắng trang | Trung bình | Gọi `localStorage.getItem("token")` bị null không được kiểm tra guard | Bổ sung auth guard ở FE: tự động hiển thị modal yêu cầu đăng nhập và redirect về `login.html` | `js/pages/my-tickets.js`<br>`js/pages/booking.js` | **ĐÃ SỬA (PASS)** |

---

## IV. MINH CHỨNG & HƯỚNG DẪN NỘP BÀI LÊN HỆ THỐNG LMS WORKLANE

1. **File Excel**:
   - File nằm tại: `E:\Project_Cinema\Test_Case_va_Test_Log_T3C572D_NguyenDinhDuc.xlsx`
   - Gồm 4 sheet: `Tổng quan & Thống kê`, `Danh sách Test Cases`, `Nhật ký Test Log`, `Bug Log & Đã sửa`.
2. **Cách nộp trên LMS Worklane Rikkei** (như trong ảnh screenshot):
   - **Cách 1 (Nộp link Google Sheet)**: Mở Google Drive cá nhân -> Tải file `Test_Case_va_Test_Log_T3C572D_NguyenDinhDuc.xlsx` lên -> Chọn "Mở bằng Google Trang tính" -> Bấm nút **Chia sẻ (Share)** -> Đặt quyền là *"Bất kỳ ai có đường liên kết đều có thể xem"* -> Dán link vào ô **Link minh chứng** trên trang task LMS và bấm **Lưu/Nộp**.
   - **Cách 2 (Nộp commit Git)**: Đã tạo commit chứa file test với mã task `T3C572D` đúng quy định của Rikkei.
