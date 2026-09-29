"""``catalog_import``: staging, review and the system vocabulary writes.

The service is pure domain logic -- no HTTP -- so every test here drives it
directly against ``db_session``. The system account's vocabulary is the only
namespace a catalog recipe may draw on (D3), so each test seeds the names it
expects to resolve and deliberately leaves the rest unknown.
"""

import pytest

import catalog
import catalog_import
import models


def entry(**overrides):
    """A well-formed uploaded entry; override one field to break it."""
    data = {
        "title": "Lentil Stew",
        "course": "main",
        "servings": 4,
        "bulk_prep": True,
        "procedure": "Simmer.",
        "image_url": None,
        "tags": ["stew"],
        "ingredients": [{"name": "Lentils", "quantity": 300.0, "unit": "g"}],
    }
    data.update(overrides)
    return data


@pytest.fixture
def vocabulary(db_session, system_account):
    """The names this module's entries expect to resolve."""
    import crud

    rows = {
        name: crud.get_or_create_ingredient(db_session, None, name, system_account.id)
        for name in ("Lentils", "Rice")
    }
    for name in ("stew", "soup"):
        crud.get_or_create_tag(db_session, name, system_account.id)
    db_session.flush()
    return rows


@pytest.fixture
def stage(db_session, admin_user, vocabulary):
    def _stage(*entries, filename="pack.json"):
        return catalog_import.stage_upload(
            db_session, admin_user, filename, list(entries)
        )

    return _stage


# --- staging -----------------------------------------------------------------

def test_stage_upload_records_the_file_and_keeps_its_order(stage, admin_user):
    batch = stage(entry(title="A"), entry(title="B"), filename="summer.json")

    assert batch.filename == "summer.json"
    assert batch.created_by_user_id == admin_user.id
    assert [item.position for item in batch.items] == [0, 1]
    assert [item.draft["title"] for item in batch.items] == ["A", "B"]


def test_a_staged_entry_starts_pending_with_its_source_intact(stage):
    uploaded = entry()
    item = stage(uploaded).items[0]

    assert item.state == "pending"
    assert item.error is None
    assert item.source == uploaded


def test_the_draft_records_which_names_already_resolve(stage, vocabulary):
    item = stage(
        entry(
            ingredients=[
                {"name": "Lentils", "quantity": 300.0, "unit": "g"},
                {"name": "Unobtanium Root", "quantity": 5.0, "unit": "g"},
            ]
        )
    ).items[0]

    resolved = {line["name"]: line["ingredient_id"] for line in item.draft["ingredients"]}
    assert resolved["Lentils"] == vocabulary["Lentils"].id
    assert resolved["Unobtanium Root"] is None


def test_export_only_fields_are_dropped_from_the_draft(stage):
    """An export file carries curation state; the draft is a recipe, not an entry."""
    item = stage(entry(status="published", published_at="2026-01-01T00:00:00")).items[0]

    assert "status" not in item.draft
    assert "published_at" not in item.draft
    # ``source`` is what was uploaded, untouched.
    assert item.source["status"] == "published"


@pytest.mark.parametrize(
    "broken",
    [
        {"servings": 0},
        {"course": "dessert"},
        {"title": ""},
        {"ingredients": [{"name": "Lentils", "quantity": -1.0, "unit": "g"}]},
        {"ingredients": [{"name": "Lentils", "quantity": 1.0, "unit": "cups"}]},
        {"tags": "stew"},
    ],
)
def test_a_malformed_entry_is_staged_invalid_with_its_reason(stage, broken):
    item = stage(entry(**broken)).items[0]

    assert item.state == "invalid"
    assert item.error


def test_one_bad_entry_never_rejects_the_file(stage):
    batch = stage(entry(title="Good"), entry(title="Bad", servings=0))

    assert [item.state for item in batch.items] == ["pending", "invalid"]


def test_a_title_collision_is_flagged_not_skipped(stage, make_catalog_recipe):
    existing = make_catalog_recipe("Lentil Stew")

    item = stage(entry(title="Lentil Stew")).items[0]

    assert item.duplicate_recipe_id == existing.id
    assert item.state == "pending"


def test_a_title_that_matches_nothing_is_not_flagged(stage, make_catalog_recipe):
    make_catalog_recipe("Something Else")

    assert stage(entry()).items[0].duplicate_recipe_id is None


# --- review ------------------------------------------------------------------

def test_update_item_replaces_the_working_copy_and_re_resolves(
    db_session, stage, vocabulary
):
    item = stage(
        entry(ingredients=[{"name": "Unknown Thing", "quantity": 1.0, "unit": "g"}])
    ).items[0]

    updated = catalog_import.update_item(
        db_session,
        item.id,
        entry(ingredients=[{"name": "Rice", "quantity": 80.0, "unit": "g"}]),
    )

    assert updated.draft["ingredients"][0]["ingredient_id"] == vocabulary["Rice"].id
    # The uploaded entry is never rewritten by an edit.
    assert updated.source["ingredients"][0]["name"] == "Unknown Thing"


def test_editing_an_invalid_item_back_into_shape_makes_it_pending(db_session, stage):
    item = stage(entry(servings=0)).items[0]
    assert item.state == "invalid"

    updated = catalog_import.update_item(db_session, item.id, entry(servings=2))

    assert updated.state == "pending"
    assert updated.error is None


def test_an_edit_that_breaks_the_item_puts_it_back_to_invalid(db_session, stage):
    item = stage(entry()).items[0]

    updated = catalog_import.update_item(db_session, item.id, entry(course="dessert"))

    assert updated.state == "invalid"
    assert updated.error


def test_problems_name_every_unresolved_ingredient_and_tag(db_session, stage):
    item = stage(
        entry(
            tags=["stew", "unheard-of-tag"],
            ingredients=[{"name": "Unobtanium Root", "quantity": 5.0, "unit": "g"}],
        )
    ).items[0]

    problems = catalog_import.item_problems(db_session, item)

    assert any("Unobtanium Root" in p for p in problems)
    assert any("unheard-of-tag" in p for p in problems)


def test_a_fully_resolved_item_has_no_problems(db_session, stage):
    item = stage(entry()).items[0]

    assert catalog_import.item_problems(db_session, item) == []


def test_skip_item_marks_it_skipped(db_session, stage):
    item = stage(entry(), entry(title="Second")).items[0]

    assert catalog_import.skip_item(db_session, item.id).state == "skipped"


# --- commit ------------------------------------------------------------------

def test_commit_item_creates_a_draft_recipe_owned_by_the_system_account(
    db_session, stage, system_account
):
    item = stage(entry(), entry(title="Second")).items[0]

    recipe = catalog_import.commit_item(db_session, item.id)

    assert recipe.user_id == system_account.id
    assert recipe.title == "Lentil Stew"
    # Publishing stays a separate action: a committed item is a draft.
    assert recipe.catalog_entry is None
    assert item.state == "committed"
    assert item.committed_recipe_id == recipe.id


def test_commit_item_writes_the_edited_draft_not_the_uploaded_source(
    db_session, stage
):
    item = stage(entry(), entry(title="Second")).items[0]
    catalog_import.update_item(db_session, item.id, entry(title="Renamed", servings=6))

    recipe = catalog_import.commit_item(db_session, item.id)

    assert (recipe.title, recipe.servings) == ("Renamed", 6)


def test_commit_item_refuses_an_unresolved_item(db_session, stage):
    item = stage(
        entry(ingredients=[{"name": "Unobtanium Root", "quantity": 5.0, "unit": "g"}])
    ).items[0]

    with pytest.raises(ValueError):
        catalog_import.commit_item(db_session, item.id)
    assert item.state == "pending"


def test_commit_item_refuses_an_item_that_is_already_finished(db_session, stage):
    item = stage(entry(), entry(title="Second")).items[0]
    catalog_import.skip_item(db_session, item.id)

    with pytest.raises(ValueError):
        catalog_import.commit_item(db_session, item.id)


# --- pruning -----------------------------------------------------------------

def test_a_batch_with_nothing_left_to_review_is_deleted(db_session, stage):
    batch = stage(entry(), entry(title="Second"))
    catalog_import.commit_item(db_session, batch.items[0].id)
    catalog_import.skip_item(db_session, batch.items[1].id)

    assert catalog_import.prune_if_finished(db_session, batch) is True
    assert db_session.get(models.CatalogImportBatch, batch.id) is None


def test_a_batch_with_an_invalid_item_left_survives(db_session, stage):
    batch = stage(entry(servings=0), entry(title="Second"))
    catalog_import.skip_item(db_session, batch.items[1].id)

    assert catalog_import.prune_if_finished(db_session, batch) is False
    assert db_session.get(models.CatalogImportBatch, batch.id) is not None


def test_a_batch_with_a_pending_item_left_survives(db_session, stage):
    batch = stage(entry(), entry(title="Second"))
    catalog_import.skip_item(db_session, batch.items[0].id)

    assert catalog_import.prune_if_finished(db_session, batch) is False


# --- system vocabulary: ingredients ------------------------------------------

def test_create_system_ingredient_lands_in_the_system_namespace(
    db_session, system_account
):
    ingredient = catalog_import.create_system_ingredient(
        db_session,
        name="Unobtanium Root",
        season_months=[1, 2],
        categories=["spice"],
        grams_per_piece=2.0,
    )

    assert ingredient.user_id == system_account.id
    assert ingredient.season_months == [1, 2]
    assert ingredient.categories == ["spice"]
    assert ingredient.grams_per_piece == 2.0


def test_create_system_ingredient_refuses_a_name_it_already_owns(
    db_session, vocabulary
):
    with pytest.raises(ValueError):
        catalog_import.create_system_ingredient(db_session, name="Lentils")


def test_update_system_ingredient_rewrites_the_fields_it_is_given(
    db_session, vocabulary
):
    updated = catalog_import.update_system_ingredient(
        db_session,
        vocabulary["Lentils"].id,
        name="Green Lentils",
        season_months=[6],
        grams_per_ml=0.8,
    )

    assert updated.name == "Green Lentils"
    assert updated.season_months == [6]
    assert updated.grams_per_ml == 0.8


def test_update_system_ingredient_refuses_an_ingredient_it_does_not_own(
    db_session, user, system_account
):
    import crud

    theirs = crud.get_or_create_ingredient(db_session, None, "Theirs", user.id)
    db_session.flush()

    with pytest.raises(LookupError):
        catalog_import.update_system_ingredient(db_session, theirs.id, name="Mine")


def test_delete_system_ingredient_removes_an_unused_one(db_session, vocabulary):
    ingredient_id = vocabulary["Rice"].id

    catalog_import.delete_system_ingredient(db_session, ingredient_id)

    assert db_session.get(models.Ingredient, ingredient_id) is None


def test_delete_system_ingredient_refuses_one_in_use_and_says_how_many(
    db_session, make_catalog_recipe, system_account
):
    make_catalog_recipe("Risotto", ingredients=(("Rice", 80, "g"),))
    rice = catalog.system_ingredients(db_session)
    rice = next(row for row in rice if row.name == "Rice")

    with pytest.raises(catalog_import.VocabularyInUse) as excinfo:
        catalog_import.delete_system_ingredient(db_session, rice.id)

    assert excinfo.value.count == 1
    assert db_session.get(models.Ingredient, rice.id) is not None


# --- system vocabulary: tags -------------------------------------------------

def test_create_system_tag_lands_in_the_system_namespace(db_session, system_account):
    tag = catalog_import.create_system_tag(
        db_session, name="brunch", penalize_repetition=True
    )

    assert tag.user_id == system_account.id
    assert tag.is_system is True
    assert tag.penalize_repetition is True


def test_create_system_tag_refuses_a_name_it_already_owns(db_session, vocabulary):
    with pytest.raises(ValueError):
        catalog_import.create_system_tag(db_session, name="stew")


def test_update_system_tag(db_session, vocabulary, system_account):
    tag = next(row for row in catalog.system_tags(db_session) if row.name == "soup")

    assert catalog_import.update_system_tag(db_session, tag.id, name="broth").name == (
        "broth"
    )


def test_update_system_tag_refuses_a_name_already_taken(db_session, vocabulary):
    tag = next(row for row in catalog.system_tags(db_session) if row.name == "soup")

    with pytest.raises(ValueError):
        catalog_import.update_system_tag(db_session, tag.id, name="stew")


def test_delete_system_tag_removes_it_whether_or_not_it_is_used(
    db_session, make_catalog_recipe
):
    """A tag carries no physics, so losing one costs a label and nothing else."""
    recipe = make_catalog_recipe("Minestrone", tags=("soup",))
    tag = next(row for row in catalog.system_tags(db_session) if row.name == "soup")

    catalog_import.delete_system_tag(db_session, tag.id)

    assert db_session.get(models.Tag, tag.id) is None
    assert [t.name for t in recipe.tags] == []


def test_tag_usage_count_reports_how_many_recipes_carry_it(
    db_session, make_catalog_recipe
):
    """The confirm dialog shows a count before the delete goes through."""
    make_catalog_recipe("Minestrone", tags=("soup",))
    tag = next(row for row in catalog.system_tags(db_session) if row.name == "soup")

    assert catalog_import.tag_usage(db_session, tag.id) == 1
