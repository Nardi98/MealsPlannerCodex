"""The legacy ``/plan`` paths are gone; ``/meal-plans`` is the only address.

``/plan/settings`` is deliberately asserted to still work: it never had a
``/meal-plans`` twin and is the current path, so a future cleanup that removed it
along with the others would be a regression rather than tidying.
"""

import main
from tests.conftest import get_route_paths


def test_the_legacy_plan_path_is_not_registered():
    assert "/plan" not in get_route_paths(main.app)


def test_the_current_meal_plans_path_is_registered():
    assert "/meal-plans" in get_route_paths(main.app)


def test_plan_settings_is_untouched():
    assert "/plan/settings" in get_route_paths(main.app)


def test_the_legacy_paths_answer_404(auth_client):
    # 404, not 401: the route does not exist, so auth never gets a say. Checked
    # for all three verbs because ``get_route_paths`` only reports GET paths.
    assert auth_client.get(
        "/plan", params={"plan_date": "2026-01-01"}
    ).status_code == 404
    assert auth_client.post("/plan", json={"plan": {}}).status_code == 404
    assert auth_client.delete(
        "/plan", params={"start_date": "2026-01-01", "end_date": "2026-01-01"}
    ).status_code == 404


def test_the_current_path_still_reads_a_plan(auth_client):
    resp = auth_client.get("/meal-plans", params={"plan_date": "2026-01-01"})
    assert resp.status_code == 200
