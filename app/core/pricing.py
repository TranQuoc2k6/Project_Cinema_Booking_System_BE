"""
Module: Pricing Engine (app/core/pricing.py)
Quản lý cấu hình giá vé theo loại ghế, phụ thu cuối tuần và khung giờ vàng.
Cung cấp hàm tính giá thống nhất cho sơ đồ ghế (seat map) và đơn đặt vé (booking).
"""
import json
import os
from datetime import datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "pricing_config.json")

# Cấu hình mặc định toàn hệ thống
DEFAULT_PRICING_CONFIG: Dict[str, Any] = {
    # 1. Hệ số nhân giá theo loại ghế
    "seat_multipliers": {
        "standard": Decimal("1.0"),
        "vip": Decimal("1.5"),
        "couple": Decimal("2.0"),
    },
    # Phụ thu cố định theo loại ghế (nếu có)
    "seat_type_surcharges": {
        "standard": Decimal("0.0"),
        "vip": Decimal("0.0"),
        "couple": Decimal("0.0"),
    },
    # 2. Phụ thu cuối tuần (Thứ 7, Chủ Nhật)
    "weekend_surcharge": Decimal("10000.00"),  # +10.000 VND / vé
    "weekend_days": [5, 6],  # 5: Thứ 7, 6: Chủ Nhật (Python weekday: 0=Mon, 6=Sun)
    "include_friday_evening": True,  # Tối thứ 6 từ 17:00 tính là cuối tuần
    "friday_evening_start_hour": 17,
    # 3. Phụ thu khung giờ vàng (18:00 - 22:00)
    "peak_hour_surcharge": Decimal("10000.00"),  # +10.000 VND / vé
    "peak_hour_start": "18:00",
    "peak_hour_end": "22:00",
}

_active_config: Dict[str, Any] = dict(DEFAULT_PRICING_CONFIG)


def _load_persisted_config() -> None:
    """Tải cấu hình đã lưu từ file JSON nếu có."""
    global _active_config
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULT_PRICING_CONFIG)
            if "seat_multipliers" in data and isinstance(data["seat_multipliers"], dict):
                merged["seat_multipliers"] = {
                    k.lower(): Decimal(str(v)) for k, v in data["seat_multipliers"].items()
                }
            if "seat_type_surcharges" in data and isinstance(data["seat_type_surcharges"], dict):
                merged["seat_type_surcharges"] = {
                    k.lower(): Decimal(str(v)) for k, v in data["seat_type_surcharges"].items()
                }
            if "weekend_surcharge" in data:
                merged["weekend_surcharge"] = Decimal(str(data["weekend_surcharge"]))
            if "peak_hour_surcharge" in data:
                merged["peak_hour_surcharge"] = Decimal(str(data["peak_hour_surcharge"]))
            if "weekend_days" in data:
                merged["weekend_days"] = list(data["weekend_days"])
            if "include_friday_evening" in data:
                merged["include_friday_evening"] = bool(data["include_friday_evening"])
            if "friday_evening_start_hour" in data:
                merged["friday_evening_start_hour"] = int(data["friday_evening_start_hour"])
            if "peak_hour_start" in data:
                merged["peak_hour_start"] = str(data["peak_hour_start"])
            if "peak_hour_end" in data:
                merged["peak_hour_end"] = str(data["peak_hour_end"])

            _active_config = merged
        except Exception as e:
            print(f"[Pricing] Lỗi đọc file config: {e}. Dùng cấu hình mặc định.")


def _save_persisted_config() -> None:
    """Lưu cấu hình hiện tại ra file JSON."""
    try:
        data = {
            "seat_multipliers": {k: float(v) for k, v in _active_config["seat_multipliers"].items()},
            "seat_type_surcharges": {k: float(v) for k, v in _active_config["seat_type_surcharges"].items()},
            "weekend_surcharge": float(_active_config["weekend_surcharge"]),
            "peak_hour_surcharge": float(_active_config["peak_hour_surcharge"]),
            "weekend_days": _active_config["weekend_days"],
            "include_friday_evening": _active_config["include_friday_evening"],
            "friday_evening_start_hour": _active_config["friday_evening_start_hour"],
            "peak_hour_start": _active_config["peak_hour_start"],
            "peak_hour_end": _active_config["peak_hour_end"],
        }
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Pricing] Không thể lưu file config: {e}")


# Tải cấu hình khi khởi động module
_load_persisted_config()


def get_pricing_config() -> Dict[str, Any]:
    """Trả về cấu hình giá hiện tại."""
    return dict(_active_config)


def update_pricing_config(new_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cập nhật cấu hình giá mới và lưu lại.
    """
    global _active_config
    if "seat_multipliers" in new_config and isinstance(new_config["seat_multipliers"], dict):
        for k, v in new_config["seat_multipliers"].items():
            _active_config["seat_multipliers"][k.lower()] = Decimal(str(v))

    if "seat_type_surcharges" in new_config and isinstance(new_config["seat_type_surcharges"], dict):
        for k, v in new_config["seat_type_surcharges"].items():
            _active_config["seat_type_surcharges"][k.lower()] = Decimal(str(v))

    if "weekend_surcharge" in new_config and new_config["weekend_surcharge"] is not None:
        _active_config["weekend_surcharge"] = Decimal(str(new_config["weekend_surcharge"]))

    if "peak_hour_surcharge" in new_config and new_config["peak_hour_surcharge"] is not None:
        _active_config["peak_hour_surcharge"] = Decimal(str(new_config["peak_hour_surcharge"]))

    if "weekend_days" in new_config and new_config["weekend_days"] is not None:
        _active_config["weekend_days"] = list(new_config["weekend_days"])

    if "include_friday_evening" in new_config and new_config["include_friday_evening"] is not None:
        _active_config["include_friday_evening"] = bool(new_config["include_friday_evening"])

    if "friday_evening_start_hour" in new_config and new_config["friday_evening_start_hour"] is not None:
        _active_config["friday_evening_start_hour"] = int(new_config["friday_evening_start_hour"])

    if "peak_hour_start" in new_config and new_config["peak_hour_start"] is not None:
        _active_config["peak_hour_start"] = str(new_config["peak_hour_start"])

    if "peak_hour_end" in new_config and new_config["peak_hour_end"] is not None:
        _active_config["peak_hour_end"] = str(new_config["peak_hour_end"])

    _save_persisted_config()
    return get_pricing_config()


def _parse_time_str(time_str: str) -> time:
    """Chuyển đổi chuỗi HH:MM thành time object."""
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]))


def is_weekend_showtime(showtime_start: Optional[datetime], config: Optional[Dict[str, Any]] = None) -> bool:
    """
    Kiểm tra xem suất chiếu có rơi vào ngày cuối tuần hay không:
    - Thứ 7 và Chủ Nhật (weekday 5 và 6).
    - Tùy chọn: Chiều/Tối Thứ 6 từ 17:00 trở đi.
    """
    if not isinstance(showtime_start, datetime):
        return False

    cfg = config or _active_config
    weekday = showtime_start.weekday()  # 0: Mon, 4: Fri, 5: Sat, 6: Sun
    weekend_days = cfg.get("weekend_days", [5, 6])

    if weekday in weekend_days:
        return True

    if cfg.get("include_friday_evening", True) and weekday == 4:
        friday_hour = cfg.get("friday_evening_start_hour", 17)
        if showtime_start.hour >= friday_hour:
            return True

    return False


def is_peak_hour_showtime(showtime_start: Optional[datetime], config: Optional[Dict[str, Any]] = None) -> bool:
    """
    Kiểm tra xem suất chiếu có rơi vào khung Giờ Vàng (Peak hours / Prime time) hay không.
    Mặc định: 18:00 đến 22:00 hàng ngày.
    """
    if not isinstance(showtime_start, datetime):
        return False

    cfg = config or _active_config
    try:
        p_start = _parse_time_str(cfg.get("peak_hour_start", "18:00"))
        p_end = _parse_time_str(cfg.get("peak_hour_end", "22:00"))
        st_time = showtime_start.time()

        if p_start <= p_end:
            return p_start <= st_time < p_end
        else:
            # Trường hợp khung giờ xuyên đêm, vd: 22:00 đến 02:00
            return st_time >= p_start or st_time < p_end
    except Exception:
        return 18 <= showtime_start.hour < 22


def get_showtime_surcharges(
    showtime_start: Optional[datetime], config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Lấy thông tin và giá trị phụ thu cho một suất chiếu.
    """
    cfg = config or _active_config
    is_weekend = is_weekend_showtime(showtime_start, cfg)
    is_peak = is_peak_hour_showtime(showtime_start, cfg)

    weekend_surcharge = cfg.get("weekend_surcharge", Decimal("10000.00")) if is_weekend else Decimal("0.00")
    peak_surcharge = cfg.get("peak_hour_surcharge", Decimal("10000.00")) if is_peak else Decimal("0.00")
    total_surcharge = weekend_surcharge + peak_surcharge

    return {
        "is_weekend": is_weekend,
        "is_peak_hour": is_peak,
        "weekend_surcharge": weekend_surcharge,
        "peak_hour_surcharge": peak_surcharge,
        "total_surcharge": total_surcharge,
    }


def calculate_seat_price(
    base_price: Any,
    seat_type: Optional[str] = "standard",
    showtime_start: Optional[datetime] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Decimal:
    """
    Tính toán giá vé cuối cùng cho một ghế dựa trên:
    1. Giá cơ bản của suất chiếu (base_price).
    2. Phụ thu cuối tuần (nếu rơi vào Thứ 7, Chủ Nhật hoặc tối Thứ 6).
    3. Phụ thu giờ vàng (nếu chiếu trong khung 18:00 - 22:00).
    4. Hệ số nhân theo loại ghế (standard: 1.0, vip: 1.5, couple: 2.0).
    5. Phụ thu cố định loại ghế (nếu có).

    Công thức:
        Giá ghế = (Giá cơ bản + Phụ thu cuối tuần + Phụ thu giờ vàng) * Hệ số loại ghế + Phụ thu loại ghế
    """
    cfg = config or _active_config

    try:
        base_dec = Decimal(str(base_price))
    except Exception:
        base_dec = Decimal("95000.00")

    # Tính phụ thu theo khung giờ chiếu
    surcharges = get_showtime_surcharges(showtime_start, cfg)
    slot_base_price = base_dec + surcharges["total_surcharge"]

    # Hệ số loại ghế
    stype = (seat_type or "standard").lower().strip()
    multipliers = cfg.get("seat_multipliers", DEFAULT_PRICING_CONFIG["seat_multipliers"])
    multiplier = multipliers.get(stype, Decimal("1.0"))

    # Phụ thu cố định loại ghế (nếu có)
    type_surcharges = cfg.get("seat_type_surcharges", DEFAULT_PRICING_CONFIG["seat_type_surcharges"])
    type_fee = type_surcharges.get(stype, Decimal("0.00"))

    final_price = (slot_base_price * multiplier + type_fee).quantize(Decimal("0.01"))
    return final_price


def get_pricing_breakdown(
    base_price: Any,
    showtime_start: Optional[datetime] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Trả về bảng phân tích chi tiết cách tính giá cho suất chiếu:
    - Giá gốc
    - Chi tiết phụ thu cuối tuần & giờ vàng
    - Giá cụ thể cho từng loại ghế (Standard, VIP, Couple)
    """
    cfg = config or _active_config
    try:
        base_dec = Decimal(str(base_price))
    except Exception:
        base_dec = Decimal("95000.00")

    surcharges = get_showtime_surcharges(showtime_start, cfg)
    slot_price = base_dec + surcharges["total_surcharge"]

    multipliers = cfg.get("seat_multipliers", DEFAULT_PRICING_CONFIG["seat_multipliers"])
    seat_prices: Dict[str, float] = {}

    for stype in ("standard", "vip", "couple"):
        p = calculate_seat_price(base_dec, stype, showtime_start, cfg)
        seat_prices[stype] = float(p)

    return {
        "base_price": float(base_dec),
        "is_weekend": surcharges["is_weekend"],
        "weekend_surcharge": float(surcharges["weekend_surcharge"]),
        "is_peak_hour": surcharges["is_peak_hour"],
        "peak_hour_surcharge": float(surcharges["peak_hour_surcharge"]),
        "total_surcharge": float(surcharges["total_surcharge"]),
        "slot_adjusted_base_price": float(slot_price),
        "seat_prices": seat_prices,
        "multipliers": {k: float(v) for k, v in multipliers.items()},
    }
