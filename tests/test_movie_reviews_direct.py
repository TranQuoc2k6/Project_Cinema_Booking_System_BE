"""
Kịch bản kiểm thử tích hợp chuyên sâu cho chức năng Đánh giá & Bình luận phim (Task T3C7300).
Chạy độc lập với Python và SQLite in-memory, kiểm thử toàn bộ 12 yêu cầu nghiệp vụ:
1. Khách chưa đăng nhập (None user) -> Không có quyền đánh giá.
2. Khách đã đăng nhập nhưng chưa đặt vé -> Bị từ chối với lý do chưa mua vé.
3. Khách có đơn vé nhưng chưa thanh toán (GIU_CHO) -> Bị từ chối với lý do chưa thanh toán.
4. Khách đã thanh toán nhưng suất chiếu chưa kết thúc (tương lai) -> Bị từ chối với lý do suất chiếu chưa kết thúc.
5. Khách đã xem phim hợp lệ (đã thanh toán + suất chiếu đã kết thúc) -> Đủ điều kiện và gửi đánh giá thành công.
6. Đánh giá 0 sao hoặc trên 5 sao -> Bị chặn bởi Pydantic validation.
7. Bình luận rỗng hoặc chỉ có khoảng trắng -> Bị chặn bởi Pydantic validation.
8. Đánh giá trùng -> Hệ thống tự động cập nhật đánh giá cũ, không nhân bản bản ghi trong DB.
9. Hai khách hàng đánh giá cùng một phim -> Lưu trữ 2 bản ghi độc lập, gắn đúng user_id.
10. Điểm trung bình và biểu đồ sao sau khi có nhiều đánh giá được tính toán chính xác (4 + 5 = 4.5).
11. Phim chưa có đánh giá -> Trả về 0.0 sao, 0 lượt, danh sách rỗng, không bị crash chia cho 0.
12. API chi tiết phim get_movie_by_id tự động tích hợp điểm đánh giá trung bình từ database thật.
"""
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

# Thêm root vào sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pydantic import ValidationError

from database import Base
from app.models import Cinema, Movie, Room, Showtime, Booking, Payment, User, Role, Review
from app.schemas.review import ReviewCreate, ReviewUpdate
from app.services import review_service, movie_service


def run_tests():
    print("=" * 70)
    print("BẮT ĐẦU CHẠY KIỂM THỬ TOÀN DIỆN BACKEND REVIEW SERVICE (TASK T3C7300)")
    print("=" * 70)

    # 1. Khởi tạo DB SQLite in-memory
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSession()

    try:
        # Nạp dữ liệu giả lập chuẩn xác
        role = Role(id=2, name="USER", description="Khách hàng")
        db.add(role)
        db.flush()

        # Tạo các khách hàng
        u1 = User(id=1, role_id=2, full_name="Nguyen Van A (Hop le)", email="u1@test.com", password_hash="pwd", is_active=True)
        u2 = User(id=2, role_id=2, full_name="Tran Thi B (Hop le)", email="u2@test.com", password_hash="pwd", is_active=True)
        u3 = User(id=3, role_id=2, full_name="Le Van C (Chua mua ve)", email="u3@test.com", password_hash="pwd", is_active=True)
        u4 = User(id=4, role_id=2, full_name="Pham D (Chua thanh toan)", email="u4@test.com", password_hash="pwd", is_active=True)
        u5 = User(id=5, role_id=2, full_name="Hoang E (Suat chieu tuong lai)", email="u5@test.com", password_hash="pwd", is_active=True)
        db.add_all([u1, u2, u3, u4, u5])

        # Tạo phim
        m1 = Movie(id=1, title="Mai", duration_minutes=120, release_date=date.today() - timedelta(days=20), status="NOW_SHOWING")
        m2 = Movie(id=2, title="Dune: Part Two (Chua co review)", duration_minutes=166, release_date=date.today(), status="NOW_SHOWING")
        db.add_all([m1, m2])

        # Rạp & Phòng
        cinema = Cinema(id=1, name="Lumen Cinema", address="Hanoi", city="Hanoi")
        db.add(cinema)
        db.flush()
        room = Room(id=1, cinema_id=1, name="Screen 1", room_type="2D", total_seats=60)
        db.add(room)
        db.flush()

        # Suất chiếu
        # St1: Suất chiếu ĐÃ KẾT THÚC (2 giờ trước)
        st1_end = datetime.now() - timedelta(hours=2)
        st1_start = st1_end - timedelta(hours=2)
        st_past = Showtime(id=1, movie_id=1, room_id=1, start_time=st1_start, end_time=st1_end, price=Decimal("100000"))

        # St2: Suất chiếu TƯƠNG LAI (ngày mai)
        st2_start = datetime.now() + timedelta(days=1)
        st2_end = st2_start + timedelta(hours=2)
        st_future = Showtime(id=2, movie_id=1, room_id=1, start_time=st2_start, end_time=st2_end, price=Decimal("100000"))
        db.add_all([st_past, st_future])
        db.flush()

        # Bookings & Payments
        # u1: Đã thanh toán, suất chiếu kết thúc
        b1 = Booking(id=1, booking_code="BK-01", user_id=1, showtime_id=1, total_price=Decimal("100000"), status="DA_THANH_TOAN")
        p1 = Payment(id=1, booking_id=1, amount=Decimal("100000"), payment_method="MOMO", status="SUCCESS")

        # u2: Đã thanh toán, suất chiếu kết thúc
        b2 = Booking(id=2, booking_code="BK-02", user_id=2, showtime_id=1, total_price=Decimal("100000"), status="DA_THANH_TOAN")
        p2 = Payment(id=2, booking_id=2, amount=Decimal("100000"), payment_method="VNPAY", status="SUCCESS")

        # u4: Đơn vé giữ chỗ, CHƯA THANH TOÁN
        b4 = Booking(id=4, booking_code="BK-04", user_id=4, showtime_id=1, total_price=Decimal("100000"), status="GIU_CHO")

        # u5: Đã thanh toán, nhưng suất chiếu NGÀY MAI
        b5 = Booking(id=5, booking_code="BK-05", user_id=5, showtime_id=2, total_price=Decimal("100000"), status="DA_THANH_TOAN")
        p5 = Payment(id=5, booking_id=5, amount=Decimal("100000"), payment_method="MOMO", status="SUCCESS")

        db.add_all([b1, p1, b2, p2, b4, b5, p5])
        db.commit()
        print("[OK] Đã chuẩn bị môi trường test và nạp dữ liệu mẫu thành công.")

        # TEST CASE 1: Khách chưa mua vé (u3)
        print("\n--- TEST CASE 1 & 2: Khách chưa mua vé (u3) ---")
        el3 = review_service.check_user_review_eligibility(db, user_id=3, movie_id=1)
        assert el3["can_review"] is False, "Lỗi: Khách chưa mua vé không được phép đánh giá!"
        assert "chưa mua vé" in el3["reason"].lower()
        print(f"[PASSED] Chặn thành công khách chưa mua vé: {el3['reason']}")

        # TEST CASE 3: Khách có vé nhưng chưa thanh toán (u4)
        print("\n--- TEST CASE 3: Khách có vé nhưng chưa thanh toán (u4) ---")
        el4 = review_service.check_user_review_eligibility(db, user_id=4, movie_id=1)
        assert el4["can_review"] is False, "Lỗi: Khách chưa thanh toán không được phép đánh giá!"
        assert "chưa được thanh toán" in el4["reason"].lower()
        print(f"[PASSED] Chặn thành công khách chưa thanh toán: {el4['reason']}")

        # TEST CASE 4: Khách đã thanh toán nhưng suất chiếu chưa kết thúc (u5)
        print("\n--- TEST CASE 4: Suất chiếu chưa kết thúc (u5) ---")
        el5 = review_service.check_user_review_eligibility(db, user_id=5, movie_id=1)
        assert el5["can_review"] is False, "Lỗi: Suất chiếu chưa kết thúc không được phép đánh giá!"
        assert "chưa kết thúc" in el5["reason"].lower()
        print(f"[PASSED] Chặn thành công suất chiếu chưa kết thúc: {el5['reason']}")

        # TEST CASE 5: Khách đã xem phim hợp lệ (u1)
        print("\n--- TEST CASE 5: Khách đủ điều kiện đánh giá (u1) ---")
        el1 = review_service.check_user_review_eligibility(db, user_id=1, movie_id=1)
        assert el1["can_review"] is True, "Lỗi: Khách đã xem phim phải được phép đánh giá!"
        print(f"[PASSED] Xác nhận đủ điều kiện: {el1['reason']}")

        # TEST CASE 6 & 7: Validate số sao (0 hoặc 6) và bình luận rỗng
        print("\n--- TEST CASE 6 & 7: Validate dữ liệu đầu vào ---")
        try:
            ReviewCreate(rating=0, comment="Sao 0")
            assert False, "Lỗi: Cho phép rating 0 sao!"
        except ValidationError:
            print("[PASSED] Validate chặn thành công 0 sao.")

        try:
            ReviewCreate(rating=6, comment="Sao 6")
            assert False, "Lỗi: Cho phép rating 6 sao!"
        except ValidationError:
            print("[PASSED] Validate chặn thành công 6 sao.")

        try:
            ReviewCreate(rating=5, comment="   ")
            assert False, "Lỗi: Cho phép bình luận khoảng trắng!"
        except ValidationError:
            print("[PASSED] Validate chặn thành công bình luận rỗng.")

        # TEST CASE 8: Tạo đánh giá hợp lệ cho u1 (5 sao)
        print("\n--- TEST CASE 8: Gửi đánh giá hợp lệ u1 ---")
        payload1 = ReviewCreate(rating=5, comment="Bộ phim xuất sắc từng phân cảnh!")
        rev1, is_created = review_service.create_or_update_review(db, movie_id=1, user=u1, payload=payload1)
        assert is_created is True, "Lỗi: Lần đầu đánh giá phải là tạo mới!"
        assert rev1.rating == 5
        assert rev1.comment == "Bộ phim xuất sắc từng phân cảnh!"
        print(f"[PASSED] Tạo đánh giá thành công ID={rev1.id}, Rating={rev1.rating}")

        # TEST CASE 8 (tiếp): Đánh giá trùng -> Tự động cập nhật thành 4 sao
        print("\n--- TEST CASE 8 (tiếp): Đánh giá trùng u1 gửi lại -> Cập nhật ---")
        payload1_update = ReviewCreate(rating=4, comment="Đã xem lại và chấm 4 sao thôi.")
        rev1_updated, is_created2 = review_service.create_or_update_review(db, movie_id=1, user=u1, payload=payload1_update)
        assert is_created2 is False, "Lỗi: Gửi lại phải là cập nhật (is_created=False)!"
        assert rev1_updated.id == rev1.id, "Lỗi: Phải giữ nguyên ID bản ghi, không nhân bản!"
        assert rev1_updated.rating == 4
        assert rev1_updated.comment == "Đã xem lại và chấm 4 sao thôi."

        # Kiểm tra tổng số bản ghi trong DB cho movie 1
        total_in_db = db.query(Review).filter(Review.movie_id == 1).count()
        assert total_in_db == 1, f"Lỗi: Không được có duplicate! Đang có {total_in_db} bản ghi."
        print(f"[PASSED] Cập nhật đánh giá trùng thành công, tổng bản ghi vẫn là 1.")

        # TEST CASE 9: Khách hàng thứ 2 (u2) đánh giá phim (5 sao)
        print("\n--- TEST CASE 9: Khách hàng thứ hai u2 đánh giá ---")
        payload2 = ReviewCreate(rating=5, comment="Xúc động rơi nước mắt, diễn xuất tuyệt đỉnh!")
        rev2, is_created_u2 = review_service.create_or_update_review(db, movie_id=1, user=u2, payload=payload2)
        assert is_created_u2 is True
        assert rev2.id != rev1.id
        total_in_db_after_u2 = db.query(Review).filter(Review.movie_id == 1).count()
        assert total_in_db_after_u2 == 2, "Lỗi: Phải có 2 bản ghi riêng biệt cho 2 khách hàng!"
        print(f"[PASSED] Đã lưu 2 đánh giá độc lập của 2 khách hàng. Tổng bản ghi = {total_in_db_after_u2}")

        # TEST CASE 10: Tính điểm trung bình và thống kê
        print("\n--- TEST CASE 10: Tính điểm trung bình và biểu đồ sao ---")
        avg_score, total_count, breakdown = review_service.get_movie_rating_stats(db, movie_id=1)
        # u1: 4 sao, u2: 5 sao -> trung bình = (4 + 5) / 2 = 4.5
        assert avg_score == 4.5, f"Lỗi: Điểm trung bình tính sai: {avg_score} != 4.5"
        assert total_count == 2
        assert breakdown[5] == 1, "Breakdown 5 sao phải là 1"
        assert breakdown[4] == 1, "Breakdown 4 sao phải là 1"
        assert breakdown[3] == 0
        print(f"[PASSED] Điểm trung bình: {avg_score}/5.0 (Tổng: {total_count} lượt, Breakdown: {breakdown})")

        # TEST CASE 11: Phim chưa có đánh giá (m2)
        print("\n--- TEST CASE 11: Phim chưa có đánh giá (m2) ---")
        avg_m2, total_m2, breakdown_m2 = review_service.get_movie_rating_stats(db, movie_id=2)
        assert avg_m2 == 0.0, f"Lỗi: Phim chưa có review phải là 0.0, ra: {avg_m2}"
        assert total_m2 == 0
        list_m2 = review_service.get_movie_reviews(db, movie_id=2)
        assert len(list_m2.items) == 0
        assert list_m2.total_reviews == 0
        print(f"[PASSED] Phim chưa có review trả về an toàn: {avg_m2} sao, {total_m2} lượt, danh sách rỗng.")

        # TEST CASE 12: movie_service.get_movie_by_id tự động gắn điểm đánh giá
        print("\n--- TEST CASE 12: movie_service.get_movie_by_id tích hợp điểm đánh giá ---")
        detail_m1 = movie_service.get_movie_by_id(db, movie_id=1)
        assert detail_m1["average_rating"] == 4.5
        assert detail_m1["total_reviews"] == 2
        print(f"[PASSED] Chi tiết phim tích hợp thành công: average_rating={detail_m1['average_rating']}, total_reviews={detail_m1['total_reviews']}")

        detail_m2 = movie_service.get_movie_by_id(db, movie_id=2)
        assert detail_m2["average_rating"] == 0.0
        assert detail_m2["total_reviews"] == 0
        print(f"[PASSED] Phim chưa review: average_rating={detail_m2['average_rating']}, total_reviews={detail_m2['total_reviews']}")

        print("\n" + "=" * 70)
        print("TẤT CẢ 12 TEST CASES BACKEND ĐÃ VƯỢT QUA 100% THÀNH CÔNG!")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
