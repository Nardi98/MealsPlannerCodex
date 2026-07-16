
import crud


def test_list_planned_titles_returns_distinct_titles_from_db(db_session, user):
    a = crud.create_recipe(db_session, user_id=user.id, title="A", servings_default=1, course="main")
    b = crud.create_recipe(db_session, user_id=user.id, title="B", servings_default=1, course="main")
    crud.create_recipe(db_session, user_id=user.id, title="C", servings_default=1, course="main")

    crud.set_meal_plan(
        db_session,
        {
            "2024-01-01": [{"main_id": a.id}, {"main_id": b.id}],
            "2024-01-02": [{"main_id": a.id}],
        },
        user.id,
    )

    titles = crud.list_planned_titles(db_session, user.id)

    assert titles == {"A", "B"}


def test_list_planned_titles_empty_when_no_plans(db_session, user):
    assert crud.list_planned_titles(db_session, user.id) == set()
