
import crud
import main
from datetime import date, timedelta

# Generation only accepts ranges from today on (F3), so these run tomorrow.
DAY = (date.today() + timedelta(days=1)).isoformat()


def test_generate_endpoint_returns_plan(db_session, user, auth_client):
    for i in range(3):
        crud.create_recipe(db_session, user_id=user.id, title=f"Meal {i}", course="main")

    response = auth_client.post(
        "/meal-plans/generate",
        json={"start": DAY, "end": DAY, "meals_per_day": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert DAY in data
    assert isinstance(data[DAY][0]["id"], int)
    assert data[DAY][0]["title"].startswith("Meal")
    assert data[DAY][0]["leftover"] is False


def test_generate_endpoint_forwards_fridge_ingredients(auth_client, monkeypatch):
    captured = {}

    def fake_generate_plan(*args, **kwargs):
        captured["fridge_ingredients"] = kwargs.get("fridge_ingredients")
        return []

    monkeypatch.setattr(main.planner, "generate_plan", fake_generate_plan)

    response = auth_client.post(
        "/meal-plans/generate",
        json={
            "start": DAY,
            "end": DAY,
            "meals_per_day": 1,
            "fridge": [
                {"ingredient_id": 5, "count": 2},
                {"ingredient_id": 7, "count": 1},
            ],
        },
    )
    assert response.status_code == 200
    assert captured["fridge_ingredients"] == {5: 2, 7: 1}


def test_generate_endpoint_sources_tag_penalty_weight_from_profile(
    auth_client, monkeypatch
):
    # Persist a profile tag-penalty weight that differs from the request default.
    auth_client.put("/plan/settings", json={"tag_penalty_weight": 2.0})

    captured = {}

    def fake_generate_plan(*args, **kwargs):
        captured["tag_penalty_weight"] = kwargs.get("tag_penalty_weight")
        return []

    monkeypatch.setattr(main.planner, "generate_plan", fake_generate_plan)

    response = auth_client.post(
        "/meal-plans/generate",
        json={"start": DAY, "end": DAY, "meals_per_day": 1},
    )
    assert response.status_code == 200
    assert captured["tag_penalty_weight"] == 2.0


# --------------------------------------------------------------------------
# Suggestion stamps and the planner log
# --------------------------------------------------------------------------
def _future(days=1):
    from datetime import date, timedelta

    return date.today() + timedelta(days=days)


def test_generate_stamps_the_latest_suggested_date_on_each_chosen_recipe(
    db_session, user, auth_client
):
    from datetime import timedelta

    recipes = [
        crud.create_recipe(db_session, user_id=user.id, title=f"Meal {i}", course="main")
        for i in range(6)
    ]
    far = _future(30)
    recipes[0].date_last_suggested = far
    db_session.flush()
    start, end = _future(1), _future(3)

    data = auth_client.post(
        "/meal-plans/generate",
        json={"start": start.isoformat(), "end": end.isoformat(), "meals_per_day": 1},
    ).json()

    latest = {}
    for day, meals in data.items():
        for meal in meals:
            latest[meal["id"]] = max(latest.get(meal["id"], start), start.fromisoformat(day))
    for r in recipes:
        db_session.refresh(r)
        if r.id == recipes[0].id:
            assert r.date_last_suggested == far  # never moved backwards
        elif r.id in latest:
            assert r.date_last_suggested == latest[r.id]
        else:
            assert r.date_last_suggested is None
    assert end - start == timedelta(days=2)


def test_generate_writes_one_planner_log_row_per_run(db_session, user, auth_client):
    from models import DevLogEntry

    for i in range(8):
        crud.create_recipe(db_session, user_id=user.id, title=f"Meal {i}", course="main")
    start, end = _future(1), _future(2)

    auth_client.post(
        "/meal-plans/generate",
        json={"start": start.isoformat(), "end": end.isoformat(), "meals_per_day": 2,
              "epsilon": 0.0},
    )

    [entry] = db_session.query(DevLogEntry).filter_by(user_id=user.id).all()
    assert (entry.channel, entry.event) == ("planner", "generate")
    assert entry.payload["params"]["start"] == start.isoformat()
    assert "LEFTOVER_HOLD_MARGIN" in entry.payload["settings"]
    slots = entry.payload["slots"]
    assert len(slots) == 4
    assert slots[0]["date"] == start.isoformat()
    assert len(slots[0]["runners_up"]) == 5
    assert "total" in slots[0]["breakdown"]


# --------------------------------------------------------------------------
# F3 / FR-19: generation never reaches into the past
# --------------------------------------------------------------------------
def test_generate_rejects_a_range_starting_before_today(db_session, user, auth_client):
    from datetime import date, timedelta

    crud.create_recipe(db_session, user_id=user.id, title="Meal", course="main")
    yesterday = date.today() - timedelta(days=1)

    resp = auth_client.post(
        "/meal-plans/generate",
        json={"start": yesterday.isoformat(), "end": _future(2).isoformat(), "meals_per_day": 1},
    )

    assert resp.status_code == 422
    assert "today" in resp.json()["detail"]


def test_generate_accepts_a_range_starting_today(db_session, user, auth_client):
    from datetime import date

    crud.create_recipe(db_session, user_id=user.id, title="Meal", course="main")
    today = date.today().isoformat()

    resp = auth_client.post(
        "/meal-plans/generate", json={"start": today, "end": today, "meals_per_day": 1}
    )

    assert resp.status_code == 200
