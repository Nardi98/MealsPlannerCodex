"""Favorite side pairings must survive an export/import round trip."""
import io
import json

import crud
import models


def test_export_includes_the_favorite_side_ids(db_session, user, make_recipe):
    main = make_recipe("Roast")
    side = make_recipe("Potatoes", "side")
    main.favorite_sides = [side]
    db_session.flush()

    payload = json.loads(crud.export_data(db_session, user.id))

    exported = {r["title"]: r for r in payload["recipes"]}
    assert exported["Roast"]["favorite_side_ids"] == [side.id]
    assert exported["Potatoes"]["favorite_side_ids"] == []


def test_import_restores_the_pairing_under_remapped_ids(db_session, user):
    """Ids are reassigned on import, so the link must be remapped, not copied."""
    payload = {
        "recipes": [
            {
                "id": 501,
                "title": "Roast",
                "servings_default": 2,
                "course": "main",
                "favorite_side_ids": [502],
            },
            {
                "id": 502,
                "title": "Potatoes",
                "servings_default": 2,
                "course": "side",
            },
        ],
        "tags": [],
        "meal_plans": [],
    }

    crud.import_data(
        io.StringIO(json.dumps(payload)),
        db_session,
        mode="merge",
        user_id=user.id,
    )

    main = (
        db_session.query(models.Recipe).filter_by(title="Roast").one()
    )
    assert [s.title for s in main.favorite_sides] == ["Potatoes"]


def test_import_drops_a_pairing_to_a_recipe_that_is_not_a_side(db_session, user):
    """The route rejects main->main pairings; import must not create them either."""
    payload = {
        "recipes": [
            {
                "id": 501,
                "title": "Roast",
                "servings_default": 2,
                "course": "main",
                "favorite_side_ids": [502, 503],
            },
            {"id": 502, "title": "Lasagne", "servings_default": 2, "course": "main"},
            {"id": 503, "title": "Potatoes", "servings_default": 2, "course": "side"},
        ],
        "tags": [],
        "meal_plans": [],
    }

    crud.import_data(
        io.StringIO(json.dumps(payload)),
        db_session,
        mode="merge",
        user_id=user.id,
    )

    main = db_session.query(models.Recipe).filter_by(title="Roast").one()
    assert [s.title for s in main.favorite_sides] == ["Potatoes"]


def test_import_tolerates_a_pairing_to_a_missing_recipe(db_session, user):
    payload = {
        "recipes": [
            {
                "id": 501,
                "title": "Roast",
                "servings_default": 2,
                "course": "main",
                "favorite_side_ids": [999],
            }
        ],
        "tags": [],
        "meal_plans": [],
    }

    crud.import_data(
        io.StringIO(json.dumps(payload)),
        db_session,
        mode="merge",
        user_id=user.id,
    )

    main = db_session.query(models.Recipe).filter_by(title="Roast").one()
    assert main.favorite_sides == []
