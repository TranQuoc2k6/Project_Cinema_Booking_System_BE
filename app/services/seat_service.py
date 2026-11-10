from typing import TypedDict


class GeneratedSeat(TypedDict):
    seat_number: str
    seat_row: str
    seat_column: int
    seat_type: str
    is_active: bool


def _row_label(row_index: int) -> str:
    """Convert a zero-based row index to spreadsheet-style labels: A...Z, AA..."""
    label = ""
    while row_index >= 0:
        row_index, remainder = divmod(row_index, 26)
        label = chr(ord("A") + remainder) + label
        row_index -= 1
    return label


def generate_seat_layout(
    rows: int,
    columns: int,
    vip_rows: int = 0,
    couple_rows: int = 0,
) -> list[GeneratedSeat]:
    """Generate seats with VIP rows followed by couple rows at the back."""
    couple_start = rows - couple_rows
    vip_start = couple_start - vip_rows
    seats: list[GeneratedSeat] = []

    for row_index in range(rows):
        row_label = _row_label(row_index)
        if row_index >= couple_start:
            seat_type = "couple"
        elif row_index >= vip_start:
            seat_type = "vip"
        else:
            seat_type = "standard"

        for column in range(1, columns + 1):
            seats.append(
                {
                    "seat_number": f"{row_label}{column:02d}",
                    "seat_row": row_label,
                    "seat_column": column,
                    "seat_type": seat_type,
                    "is_active": True,
                }
            )

    return seats
