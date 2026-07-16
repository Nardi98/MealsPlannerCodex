"""The per-user seed script must agree with the app on email casing."""
from scripts.seed_user_data import get_or_create_user

import crud


def test_get_or_create_user_stores_email_lowercased(db_session):
    user = get_or_create_user(db_session, "Seed.User@Example.COM", "pw12345")

    assert user.email == "seed.user@example.com"


def test_get_or_create_user_reuses_account_when_case_differs(db_session):
    existing = crud.create_user(
        db_session, email="seed@example.com", hashed_password="hp"
    )

    found = get_or_create_user(db_session, "SEED@Example.com", "pw12345")

    assert found.id == existing.id
    assert db_session.query(crud.User).count() == 1, "must not create a duplicate"
