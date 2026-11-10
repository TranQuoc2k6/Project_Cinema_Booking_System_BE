import unittest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Cinema, Room
from app.routers.seats import generate_room_seat_map
from app.schemas.seat import SeatMapGenerateRequest
from app.services.seat_service import generate_seat_layout
from database import Base


class SeatMapTests(unittest.TestCase):
    def test_generate_layout_assigns_standard_vip_and_couple_rows(self):
        seats = generate_seat_layout(rows=5, columns=3, vip_rows=1, couple_rows=2)

        self.assertEqual(len(seats), 15)
        self.assertEqual(
            [seat["seat_type"] for seat in seats[::3]],
            ["standard", "standard", "vip", "couple", "couple"],
        )
        self.assertEqual(
            seats[0],
            {
                "seat_number": "A01",
                "seat_row": "A",
                "seat_column": 1,
                "seat_type": "standard",
                "is_active": True,
            },
        )
        self.assertEqual(seats[-1]["seat_number"], "E03")

    def test_generate_layout_uses_multi_letter_row_labels(self):
        seats = generate_seat_layout(rows=28, columns=1)

        self.assertEqual(seats[25]["seat_row"], "Z")
        self.assertEqual(seats[26]["seat_row"], "AA")
        self.assertEqual(seats[27]["seat_number"], "AB01")

    def test_generate_request_rejects_invalid_layouts(self):
        invalid_layouts = (
            (
                {"rows": 2, "columns": 3, "vip_rows": 2, "couple_rows": 1},
                "không được vượt",
            ),
            ({"rows": 50, "columns": 50}, "2000 ghế"),
        )
        for values, message in invalid_layouts:
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValidationError, message):
                    SeatMapGenerateRequest(**values)

    def test_generate_endpoint_persists_layout_and_refuses_overwrite(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                cinema = Cinema(
                    name="Test cinema",
                    address="Test address",
                    city="Test city",
                )
                db.add(cinema)
                db.flush()
                room = Room(cinema_id=cinema.id, name="Room 1", total_seats=0)
                db.add(room)
                db.flush()

                response = generate_room_seat_map(
                    room_id=room.id,
                    layout=SeatMapGenerateRequest(
                        rows=3,
                        columns=2,
                        vip_rows=1,
                        couple_rows=1,
                    ),
                    db=db,
                )

                self.assertEqual(response.total_seats, 6)
                self.assertEqual(room.total_seats, 6)
                self.assertEqual(
                    [seat.seat_type.value for seat in response.seats[::2]],
                    ["standard", "vip", "couple"],
                )

                with self.assertRaises(HTTPException) as error:
                    generate_room_seat_map(
                        room_id=room.id,
                        layout=SeatMapGenerateRequest(rows=1, columns=1),
                        db=db,
                    )
                self.assertEqual(error.exception.status_code, 409)
        finally:
            Base.metadata.drop_all(engine)
            engine.dispose()
