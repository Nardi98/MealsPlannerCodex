"""``/meal-plans`` is the only plan path, and ``/plan/settings`` is not legacy.

The second half is the point of this file. ``/plan/settings`` *looks* like a
leftover of the retired ``/plan`` routes and is not: it never had a
``/meal-plans`` twin, so a later cleanup sweeping up "the rest of the /plan
routes" would take plan settings with it.

The absence of ``/plan`` is asserted over HTTP rather than against the routing
table because ``conftest.get_route_paths`` reports GET paths only -- a re-added
``@app.post("/plan")`` would slip past a table check.
"""

import main
from tests.conftest import get_route_paths


def test_plan_settings_is_still_registered():
    assert "/plan/settings" in get_route_paths(main.app)


def test_the_legacy_plan_paths_answer_404(auth_client):
    # 404, not 401: the route does not exist, so auth never gets a say.
    assert auth_client.get(
        "/plan", params={"plan_date": "2026-01-01"}
    ).status_code == 404
    assert auth_client.post("/plan", json={"plan": {}}).status_code == 404
    assert auth_client.delete(
        "/plan", params={"start_date": "2026-01-01", "end_date": "2026-01-01"}
    ).status_code == 404


def test_the_current_path_reads_a_plan(auth_client):
    resp = auth_client.get("/meal-plans", params={"plan_date": "2026-01-01"})
    assert resp.status_code == 200
