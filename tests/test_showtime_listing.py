from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Cinema, Movie, Room, Showtime
from database import Base, get_db
from main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with test_session() as db:
        cinema_one = Cinema(name="Cinema One", address="Address 1", city="Hanoi")
        cinema_two = Cinema(name="Cinema Two", address="Address 2", city="Hanoi")
        movie_one = Movie(
            title="Movie One",
            duration_minutes=120,
            release_date=date.today(),
        )
        movie_two = Movie(
            title="Movie Two",
            duration_minutes=100,
            release_date=date.today(),
        )
        db.add_all([cinema_one, cinema_two, movie_one, movie_two])
        db.flush()

        room_one = Room(cinema_id=cinema_one.id, name="Room 1", total_seats=10)
        room_two = Room(cinema_id=cinema_two.id, name="Room 2", total_seats=10)
        db.add_all([room_one, room_two])
        db.flush()

        tomorrow = date.today() + timedelta(days=1)
        day_after_tomorrow = tomorrow + timedelta(days=1)
        db.add_all(
            [
                Showtime(
                    movie_id=movie_one.id,
                    room_id=room_one.id,
                    start_time=datetime.combine(tomorrow, time(10)),
                    end_time=datetime.combine(tomorrow, time(12)),
                    price=Decimal("100000.00"),
                ),
                Showtime(
                    movie_id=movie_two.id,
                    room_id=room_one.id,
                    start_time=datetime.combine(tomorrow, time(13)),
                    end_time=datetime.combine(tomorrow, time(14, 40)),
                    price=Decimal("90000.00"),
                ),
                Showtime(
                    movie_id=movie_one.id,
                    room_id=room_two.id,
                    start_time=datetime.combine(tomorrow, time(15)),
                    end_time=datetime.combine(tomorrow, time(17)),
                    price=Decimal("110000.00"),
                ),
                Showtime(
                    movie_id=movie_one.id,
                    room_id=room_one.id,
                    start_time=datetime.combine(day_after_tomorrow, time(10)),
                    end_time=datetime.combine(day_after_tomorrow, time(12)),
                    price=Decimal("100000.00"),
                ),
                Showtime(
                    movie_id=movie_one.id,
                    room_id=room_one.id,
                    start_time=datetime.now() - timedelta(hours=1),
                    end_time=datetime.now() + timedelta(hours=1),
                    price=Decimal("100000.00"),
                ),
            ]
        )
        db.commit()
        movie_one_id = movie_one.id
        cinema_one_id = cinema_one.id

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, movie_one_id, cinema_one_id, tomorrow.isoformat()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_list_showtimes_filters_and_groups_by_cinema(client):
    test_client, movie_id, _, show_date = client

    response = test_client.get(
        "/api/showtimes",
        params={"movieId": movie_id, "date": show_date},
    )

    assert response.status_code == 200
    body = response.json()
    assert [group["cinema"]["name"] for group in body] == [
        "Cinema One",
        "Cinema Two",
    ]
    assert [item["movie_title"] for group in body for item in group["showtimes"]] == [
        "Movie One",
        "Movie One",
    ]
    assert all(
        item["start_time"].startswith(show_date)
        for group in body
        for item in group["showtimes"]
    )


def test_list_showtimes_filters_cinema_and_excludes_started_showtimes(client):
    test_client, _, cinema_id, _ = client

    response = test_client.get(
        "/api/showtimes",
        params={"cinemaId": cinema_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["cinema"]["id"] == cinema_id
    assert all(
        datetime.fromisoformat(item["start_time"]) >= datetime.now()
        for item in body[0]["showtimes"]
    )
    assert all(
        item["start_time"][:10] != (date.today() - timedelta(days=1)).isoformat()
        for item in body[0]["showtimes"]
    )


def test_list_showtimes_rejects_non_positive_movie_id(client):
    test_client, _, _, _ = client

    response = test_client.get("/api/showtimes", params={"movieId": 0})

    assert response.status_code == 422
