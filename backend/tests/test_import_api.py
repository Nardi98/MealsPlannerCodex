"""Behaviour of ``POST /data/import`` and the failure paths behind it.

``tests/test_import_export.py`` covers ``crud.import_data`` directly; this file
covers what the *user* is told, which is where the import went wrong: a no-op
import used to answer ``{"status": "ok"}`` and every real error arrived as the
same flat "Malformed import data".
"""

import io
import json

import pytest

import crud


def _payload(**overrides):
    """A minimal, valid one-recipe export payload."""
    recipe = {
        "id": 1,
        "title": "Gazpacho",
        "course": "first-course",
        "servings": 4,
        "ingredients": [
            {"id": None, "name": "Tomato", "quantity": 500, "unit": "g"},
        ],
        "tags": [7],
    }
    data = {
        "recipes": [recipe],
        "tags": [{"id": 7, "name": "summer"}],
        "meal_plans": [],
    }
    data.update(overrides)
    return data


def _unitless_payload():
    """A payload the import must reject: a quantity with nothing to measure it in."""
    data = _payload()
    data["recipes"][0]["ingredients"][0]["unit"] = None
    return data


def test_import_reports_the_real_reason_it_failed(db_session, user):
    with pytest.raises(ValueError) as excinfo:
        crud.import_data(
            io.StringIO(json.dumps(_unitless_payload())),
            db_session,
            mode="merge",
            user_id=user.id,
        )
    message = str(excinfo.value)
    assert "Gazpacho" in message
    assert "Tomato" in message


def test_import_endpoint_passes_the_real_reason_through(auth_client):
    resp = auth_client.post("/data/import?mode=merge", json=_unitless_payload())
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "Gazpacho" in detail
    assert "Tomato" in detail


def test_unreadable_payload_still_reports_malformed(db_session, user):
    with pytest.raises(ValueError, match="Malformed import data"):
        crud.import_data(
            io.StringIO("not json at all"),
            db_session,
            mode="merge",
            user_id=user.id,
        )


def test_import_endpoint_reports_what_it_imported(auth_client):
    resp = auth_client.post("/data/import?mode=merge", json=_payload())
    assert resp.status_code == 200
    assert resp.json()["imported"] == {
        "recipes": 1,
        "ingredients": 1,
        "tags": 1,
        "meal_plans": 0,
    }


def test_an_empty_import_reports_zero_rather_than_success(auth_client):
    resp = auth_client.post("/data/import?mode=merge", json={})
    assert resp.status_code == 200
    assert resp.json()["imported"] == {
        "recipes": 0,
        "ingredients": 0,
        "tags": 0,
        "meal_plans": 0,
    }


def test_an_ingredient_already_in_the_pantry_is_not_counted_as_imported(
    db_session, user, auth_client
):
    crud.get_or_create_ingredient(db_session, None, "Tomato", user_id=user.id)
    db_session.flush()

    resp = auth_client.post("/data/import?mode=merge", json=_payload())
    assert resp.json()["imported"]["ingredients"] == 0


def test_a_failed_overwrite_leaves_the_account_untouched(api_client):
    """The wipe and the reload are one transaction.

    ``clear_data`` used to commit on its own, so an import that failed after it
    left the account empty with nothing to restore it from -- and the alpha runs
    without database backups. This needs the committing ``api_client``: the
    account has to be genuinely persisted before the failing import runs.
    """
    created = api_client.post("/recipes", json={"title": "Something Precious"})
    assert created.status_code in (200, 201)

    resp = api_client.post("/data/import?mode=overwrite", json=_unitless_payload())
    assert resp.status_code == 400

    titles = [r["title"] for r in api_client.get("/recipes").json()]
    assert titles == ["Something Precious"]


def test_a_successful_overwrite_still_replaces_everything(api_client):
    """The atomicity fix must not have turned overwrite into a merge."""
    api_client.post("/recipes", json={"title": "Old Recipe"})

    resp = api_client.post("/data/import?mode=overwrite", json=_payload())
    assert resp.status_code == 200

    titles = [r["title"] for r in api_client.get("/recipes").json()]
    assert titles == ["Gazpacho"]
