"""Step 3a schema tests: ownership columns + per-user uniqueness + meal_plans PK.

These are model-level tests proving that two users can independently hold
same-named tags/ingredients and same-date meal plans, and that uniqueness is
now scoped per user rather than global.
"""

from datetime import date

import pytest

from models import Ingredient, Meal, MealPlan, Tag, User


def _make_user(db_session, email):
    user = User(email=email, hashed_password="x", auth_provider="local")
    db_session.add(user)
    db_session.flush()
    return user


def test_two_users_same_named_tag(db_session):
    a = _make_user(db_session, "a@x.test")
    b = _make_user(db_session, "b@x.test")
    db_session.add_all([
        Tag(name="pasta", user_id=a.id),
        Tag(name="pasta", user_id=b.id),
    ])
    db_session.commit()
    assert db_session.query(Tag).filter_by(name="pasta").count() == 2


def test_same_user_duplicate_tag_rejected(db_session):
    a = _make_user(db_session, "a@x.test")
    db_session.add_all([
        Tag(name="pasta", user_id=a.id),
        Tag(name="pasta", user_id=a.id),
    ])
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()


def test_two_users_same_named_ingredient(db_session):
    a = _make_user(db_session, "a@x.test")
    b = _make_user(db_session, "b@x.test")
    db_session.add_all([
        Ingredient(name="Tomato", user_id=a.id),
        Ingredient(name="Tomato", user_id=b.id),
    ])
    db_session.commit()
    assert db_session.query(Ingredient).filter_by(name="Tomato").count() == 2


def test_same_user_duplicate_ingredient_rejected(db_session):
    a = _make_user(db_session, "a@x.test")
    db_session.add_all([
        Ingredient(name="Tomato", user_id=a.id),
        Ingredient(name="Tomato", user_id=a.id),
    ])
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()


def test_two_users_same_date_meal_plan(db_session):
    a = _make_user(db_session, "a@x.test")
    b = _make_user(db_session, "b@x.test")
    day = date(2026, 1, 1)
    db_session.add_all([
        MealPlan(plan_date=day, user_id=a.id),
        MealPlan(plan_date=day, user_id=b.id),
    ])
    db_session.commit()
    assert db_session.query(MealPlan).filter_by(plan_date=day).count() == 2


def test_meals_scoped_by_user(db_session):
    a = _make_user(db_session, "a@x.test")
    b = _make_user(db_session, "b@x.test")
    day = date(2026, 1, 1)
    db_session.add_all([
        MealPlan(plan_date=day, user_id=a.id),
        MealPlan(plan_date=day, user_id=b.id),
    ])
    db_session.flush()
    db_session.add_all([
        Meal(user_id=a.id, plan_date=day, meal_number=1),
        Meal(user_id=b.id, plan_date=day, meal_number=1),
    ])
    db_session.commit()
    assert db_session.query(Meal).filter_by(plan_date=day, meal_number=1).count() == 2
