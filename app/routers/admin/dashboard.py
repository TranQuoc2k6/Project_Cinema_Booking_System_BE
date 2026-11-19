from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from app.services import dashboard_service

router = APIRouter(
    prefix="/dashboard",
    tags=["Admin: Dashboard"],
)


@router.get("/stats", summary="Thống kê toàn diện Dashboard Quản trị (Doanh thu, Vé bán, Lấp đầy, Theo phim)")
def get_dashboard_stats(
    days: int = Query(7, ge=1, le=90, description="Khoảng thời gian thống kê (7, 14, 30 ngày)"),
    db: Session = Depends(get_db)
):
    """
    Cung cấp số liệu thống kê phân tích thời gian thực dành cho Quản trị viên (SRS 1.4):
    - Thẻ chỉ số KPI (Tổng doanh thu, Doanh thu hôm nay, Vé bán, Tỷ lệ lấp đầy TB, Phim chiếu, Khách hàng)
    - Thống kê Doanh thu & Số vé bán theo ngày (kèm dữ liệu biểu đồ)
    - Thống kê Doanh thu & Số vé bán theo từng bộ phim (Box office)
    - Tỷ lệ lấp đầy theo suất chiếu / phòng chiếu (Occupancy Rate)
    - Danh sách đơn đặt vé trực tuyến mới nhất
    """
    try:
        return dashboard_service.get_dashboard_full_stats(db=db, days=days)
    except Exception as e:
        # Fallback an toàn nếu có lỗi kết nối đột ngột
        return {
            "status": "error",
            "message": str(e),
            "data": {
                "total_revenue": 0.0,
                "today_revenue": 0.0,
                "total_tickets": 0,
                "today_tickets": 0,
                "total_movies": 0,
                "total_users": 0,
                "occupancy_rate": 0.0,
                "kpi": {
                    "total_revenue": 0.0,
                    "today_revenue": 0.0,
                    "total_tickets": 0,
                    "today_tickets": 0,
                    "total_movies": 0,
                    "total_users": 0,
                    "avg_occupancy_rate": 0.0,
                    "top_movie": None
                },
                "revenue_by_day": [],
                "revenue_by_movie": [],
                "occupancy_by_showtime": [],
                "recent_bookings": []
            }
        }
