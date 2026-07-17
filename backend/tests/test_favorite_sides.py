"""The main -> favorite sides link that drives automatic side assignment."""
import models


def _reload(db_session, recipe_id):
    """Re-read a recipe as a brand-new instance.

    ``expunge_all`` matters: without it the identity map hands back the same
    object, so a plain Python attribute would masquerade as a persisted one and
    the test would pass without any mapping behind it.
    """
    db_session.flush()
    db_session.expunge_all()
    return db_session.get(models.Recipe, recipe_id)


def test_favorite_sides_persist_against_the_main(db_session, make_recipe):
    main = make_recipe("Roast Chicken")
    main.favorite_sides = [
        make_recipe("Mashed Potatoes", "side"),
        make_recipe("Steamed Broccoli", "side"),
    ]

    reloaded = _reload(db_session, main.id)

    assert {s.title for s in reloaded.favorite_sides} == {
        "Mashed Potatoes",
        "Steamed Broccoli",
    }


def test_main_has_no_favorite_sides_by_default(db_session, make_recipe):
    main = make_recipe("Plain Steak")

    assert _reload(db_session, main.id).favorite_sides == []


def test_the_link_is_directional_main_to_side(db_session, make_recipe):
    """A side must not inherit its main as one of *its* favorites."""
    main = make_recipe("Pork Chop")
    side = make_recipe("Apple Sauce", "side")
    main.favorite_sides = [side]

    assert _reload(db_session, side.id).favorite_sides == []


def test_deleting_a_favorite_side_drops_the_link_and_keeps_the_main(
    db_session, make_recipe
):
    """Agreed behaviour: removing a side recipe is silently allowed."""
    main = make_recipe("Roast Beef")
    potatoes = make_recipe("Roast Potatoes", "side")
    main.favorite_sides = [potatoes]
    db_session.flush()

    db_session.delete(potatoes)

    reloaded = _reload(db_session, main.id)
    assert reloaded.favorite_sides == []
    assert reloaded.title == "Roast Beef"
