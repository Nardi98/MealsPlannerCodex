"""The catalog export (spec §9.1, EXP-1..5, PRV-8).

The round trip ends in ``populate_from_pack``, which commits; the shared
``db_session`` scopes that commit to a SAVEPOINT (see ``conftest.py``).
"""

import json
from datetime import datetime

import pytest

import catalog
from main import app
from tests.conftest import client_as, remove_system_catalog

PACK_KEYS = {"title", "course", "servings", "bulk_prep", "tags", "procedure", "ingredients"}
EXPORT_KEYS = PACK_KEYS | {"status", "published_at", "retired_at"}


@pytest.fixture
def admin(db_session, admin_user, system_account):
    try:
        yield client_as(db_session, admin_user)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def two_entries(db_session, make_catalog_recipe, other_user):
    live = make_catalog_recipe(
        "Tomato pasta",
        course="first-course",
        ingredients=(("Pasta", 80, "g"), ("Tomato", 2, "piece"), ("Olive Oil", 10, "ml")),
        tags=("pasta", "vegan"),
        procedure="Boil. Toss.",
        servings=2,
    )
    gone = make_catalog_recipe(
        "Egg fried rice",
        ingredients=(("Rice", 150, "g"), ("Egg", 2, "piece")),
        tags=("rice", "quick"),
        status="retired",
        bulk_prep=True,
    )
    catalog.adopt(db_session, other_user, [live.id])
    return live, gone


def _export(admin):
    response = admin.get("/admin/catalog/export")
    assert response.status_code == 200, response.text
    return response


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def test_the_export_holds_every_entry_with_exactly_the_export_keys(admin, two_entries):
    """EXP-1 / EXP-2 / EXP-4, ordered by title."""
    body = _export(admin).json()

    assert [item["title"] for item in body] == ["Egg fried rice", "Tomato pasta"]
    assert all(set(item) == EXPORT_KEYS for item in body)
    retired, published = body
    assert retired["status"] == "retired"
    assert datetime.fromisoformat(retired["retired_at"])
    assert published["status"] == "published"
    assert published["retired_at"] is None
    assert all(isinstance(item["published_at"], str) and datetime.fromisoformat(item["published_at"])
               for item in body)

    assert published["course"] == "first-course"
    assert published["servings"] == 2
    assert published["bulk_prep"] is False and retired["bulk_prep"] is True
    assert published["procedure"] == "Boil. Toss."
    assert sorted(published["tags"]) == ["pasta", "vegan"]
    assert all(set(line) == {"name", "quantity", "unit"} for line in published["ingredients"])
    assert sorted((i["name"], i["quantity"], i["unit"]) for i in published["ingredients"]) == [
        ("Olive Oil", 10, "ml"), ("Pasta", 80, "g"), ("Tomato", 2, "piece"),
    ]


def test_the_export_contains_no_user_data(admin, two_entries, other_user, admin_user, system_account):
    """EXP-3 / PRV-8: no ids, counts, emails or handles -- the system account's included."""
    response = _export(admin)

    keys = set(_walk_keys(response.json()))
    assert keys.isdisjoint({"id", "user_id", "adoption_count", "email", "username", "in_my_book"})
    for secret in (
        "adoption_count", "user_id", "mealplanner",
        other_user.email, other_user.username, admin_user.email, admin_user.username,
        system_account.email, system_account.username,
    ):
        assert secret not in response.text


def test_export_catalog_service_matches_the_route(admin, db_session, two_entries):
    assert catalog.export_catalog(db_session) == _export(admin).json()


def test_the_export_body_is_the_service_output_byte_for_byte(admin, db_session, two_entries):
    """The route's local models only validate: they add, drop and reshape nothing."""
    expected = json.dumps(
        catalog.export_catalog(db_session), ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")

    assert _export(admin).content == expected


def test_an_export_round_trips_through_the_pack_loader(admin, db_session, two_entries, tmp_path):
    """EXP-5: export, empty the catalog, load the file: every entry is back, published."""
    exported = _export(admin).json()
    path = tmp_path / "export.json"
    path.write_text(json.dumps(exported), encoding="utf-8")

    remove_system_catalog(db_session)
    db_session.commit()
    created = catalog.populate_from_pack(db_session, path=path)

    assert created == len(exported) == 2
    reloaded = catalog.export_catalog(db_session)
    assert [item["status"] for item in reloaded] == ["published", "published"]
    assert all(item["retired_at"] is None for item in reloaded)

    def content(items):
        return [
            {**{k: item[k] for k in PACK_KEYS - {"tags", "ingredients"}},
             "tags": sorted(item["tags"]),
             "ingredients": sorted((i["name"], i["quantity"], i["unit"]) for i in item["ingredients"])}
            for item in items
        ]

    assert content(reloaded) == content(exported)
