# Legacy `/plan` Path Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the frontend off the legacy `/plan` API paths onto `/meal-plans`, then delete the legacy routes from the backend.

**Architecture:** Three plan routes are currently double-registered as stacked FastAPI decorators on a single handler, so `/plan` and `/meal-plans` are the *same* code reached by two URLs. That means the migration is purely a change of address: the frontend can switch over with no backend change at all, and the legacy decorators can then be deleted without touching any handler body. The work is ordered so the test suite is green after every task — the backend's own tests are moved off `/plan` *before* the routes are removed, never after.

**Tech Stack:** FastAPI + `TestClient` (pytest) on the backend; Vite/React with vitest on the frontend. No new dependencies.

---

## Why this is not just a find-and-replace

Four traps, each verified against the code at the time of writing:

1. **`/plan/settings` is NOT legacy.** `plan_settings` and `update_plan_settings` have no `/meal-plans` twin — `/plan/settings` is the current and only path for plan settings. `frontend-v2/src/api/planSettingsApi.js` is correct as it stands. **Do not touch it.**
2. **`"/plan"` appears in tests as a `page_path` *value*, not a route.** `backend/tests/test_user_feedback_admin.py:141,150` and `backend/tests/test_user_feedback_routes.py:61,66` pass `/plan` as feedback metadata. The same is true in `frontend-v2/src/api/__tests__/userFeedbackApi.test.js:27,40` and `frontend-v2/src/components/__tests__/FeedbackModal.test.jsx:27,76`. **Leave all eight alone.**
3. **The frontend page route is `/meal-plan`, not `/plan`** (`frontend-v2/src/App.jsx:216`). Browser routes are unrelated to API paths; nothing in this plan changes them.
4. **Deploy order matters once Task 4 lands.** `web` and `api` are separate Railway services. A browser holding a cached bundle that still calls `/plan` will get a 404 on plan load/save/delete the moment `api` ships without the legacy routes. **Deploy `web` first, confirm it, then `api`.** See the Deployment section at the end.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `frontend-v2/src/api/mealPlansApi.js` | The only module that addresses the plan API | Modify: 3 URLs; delete the dead suffix parser |
| `frontend-v2/src/api/__tests__/mealPlansApi.test.js` | Its unit tests | Modify: assert URLs; replace the suffix test |
| `backend/tests/test_plan_range_api.py` | Range read | Modify: 1 call site |
| `backend/tests/test_plan_delete_api.py` | Range delete | Modify: 1 call site |
| `backend/tests/test_plan_conflict_api.py` | 409 conflict flow | Modify: 1 call site |
| `backend/tests/test_feedback.py` | Accept/reject feedback | Modify: 1 call site |
| `backend/tests/test_side_dish_api.py` | Side-dish management | Modify: 6 call sites |
| `backend/tests/test_legacy_plan_paths_removed.py` | **New.** Locks in that `/plan` is gone and `/meal-plans` still works | Create |
| `backend/main.py` | Route definitions | Modify: delete 3 legacy decorators + the deprecation comment |
| `CLAUDE.md` | Project guidance | Modify: delete the "Legacy `/plan` paths" bullet |

---

### Task 1: Point `mealPlansApi` at `/meal-plans`

Three call sites. `client.js` builds its URL as `` `${API_BASE_URL}${path}` ``, and `frontend-v2/.env` sets
`VITE_API_BASE_URL=http://localhost:8000`, which vitest loads — so `fetch` receives an **absolute** URL,
not a bare path. Assert on path+query only, or the tests are coupled to that base. A guard written as
`url.startsWith('/plan')` would pass vacuously against an absolute URL, which is why the predicate below
has its own test.

**Files:**
- Modify: `frontend-v2/src/api/mealPlansApi.js:20`, `:50`, `:56`
- Test: `frontend-v2/src/api/__tests__/mealPlansApi.test.js`

- [ ] **Step 1: Write the failing tests**

Append to `frontend-v2/src/api/__tests__/mealPlansApi.test.js`:

```javascript
// `VITE_API_BASE_URL` is set in .env, so fetch receives an absolute URL. Compare
// on path+query alone so these tests hold whatever the base is configured to.
const fetchedPaths = () =>
  globalThis.fetch.mock.calls.map(([url]) => {
    const { pathname, search } = new URL(url, 'http://base.invalid')
    return `${pathname}${search}`
  })

const isLegacyPlanPath = (p) => p === '/plan' || p.startsWith('/plan?')

test('fetchRange requests the /meal-plans path', async () => {
  respondWith({})

  await mealPlansApi.fetchRange('2026-08-24', '2026-08-31')

  expect(fetchedPaths()).toEqual([
    '/meal-plans?start_date=2026-08-24&end_date=2026-08-31',
  ])
})

test('create posts to /meal-plans, and carries force through', async () => {
  respondWith({})

  await mealPlansApi.create({ plan: {} })
  await mealPlansApi.create({ plan: {} }, { force: true })

  expect(fetchedPaths()).toEqual(['/meal-plans', '/meal-plans?force=true'])
  expect(globalThis.fetch.mock.calls[0][1]).toMatchObject({ method: 'POST' })
})

test('deleteRange deletes on the /meal-plans path', async () => {
  respondWith({ deleted: 0 })

  await mealPlansApi.deleteRange('2026-08-24', '2026-08-31')

  expect(fetchedPaths()).toEqual([
    '/meal-plans?start_date=2026-08-24&end_date=2026-08-31',
  ])
  expect(globalThis.fetch.mock.calls[0][1]).toMatchObject({ method: 'DELETE' })
})

test('no mealPlansApi method addresses the legacy /plan path', async () => {
  // Guards the migration against regressing. `/plan/settings` is a different,
  // current endpoint and belongs to planSettingsApi, so it must not match here.
  respondWith({})

  await mealPlansApi.fetchRange('2026-08-24', '2026-08-24')
  await mealPlansApi.create({ plan: {} })
  await mealPlansApi.deleteRange('2026-08-24', '2026-08-24')

  expect(fetchedPaths()).toHaveLength(3)
  expect(fetchedPaths().filter(isLegacyPlanPath)).toEqual([])
})

test('the legacy-path guard would catch a regression', async () => {
  // Proves the guard above can fail: without this, a base-URL change could make
  // `isLegacyPlanPath` silently match nothing and the guard pass vacuously.
  expect(isLegacyPlanPath('/plan')).toBe(true)
  expect(isLegacyPlanPath('/plan?start_date=2026-08-24')).toBe(true)
  expect(isLegacyPlanPath('/plan/settings')).toBe(false)
  expect(isLegacyPlanPath('/meal-plans')).toBe(false)
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `frontend-v2/`:
```bash
npm run test -- src/api/__tests__/mealPlansApi.test.js
```
Expected: **4 failed, 3 passed (7)**. The four new path assertions fail, reporting `/plan?start_date=...`, `/plan` and `/plan?force=true`. `the legacy-path guard would catch a regression` passes immediately — it tests the predicate, not the code — and so do the two pre-existing tests.

- [ ] **Step 3: Change the three URLs**

In `frontend-v2/src/api/mealPlansApi.js`, `fetchRange` (line 20):

```javascript
    const data = await request(
      `/meal-plans?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
    );
```

`create` (line 50):

```javascript
  create: (payload, { force = false } = {}) =>
    request(`/meal-plans${force ? '?force=true' : ''}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
```

`deleteRange` (line 56):

```javascript
  deleteRange: (startDate, endDate) =>
    request(
      `/meal-plans?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
      {
        method: 'DELETE',
      },
    ),
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
npm run test -- src/api/__tests__/mealPlansApi.test.js
```
Expected: PASS, including the two pre-existing tests.

- [ ] **Step 5: Run the whole frontend suite and the linter**

```bash
npm run test
npm run lint
```
Expected: all green. `MealPlanPage` calls these methods through `mealPlansApi`, never by URL, so nothing else should move.

- [ ] **Step 6: Commit**

```bash
git add frontend-v2/src/api/mealPlansApi.js frontend-v2/src/api/__tests__/mealPlansApi.test.js
git commit -m "Address the plan API at /meal-plans, not the legacy /plan"
```

---

### Task 2: Delete the dead `" (leftover)"` title parsing

`crud.meal_item` returns `"recipe": meal.recipe.title` and `"leftover": meal.leftover` as separate fields, and no backend code appends a suffix to a title — so this branch can never fire against the real server. Worse, it *corrupts* a legitimate title that happens to end in `" (leftover)"`. The existing test at line 17 asserts the dead behaviour and is replaced here.

**Files:**
- Modify: `frontend-v2/src/api/mealPlansApi.js:6-15`
- Test: `frontend-v2/src/api/__tests__/mealPlansApi.test.js:17-26`

- [ ] **Step 1: Replace the suffix test with one for the real contract**

In `frontend-v2/src/api/__tests__/mealPlansApi.test.js`, delete this test entirely:

```javascript
test('fetchRange strips the "(leftover)" suffix into the leftover flag', async () => {
  respondWith({
    '2026-08-24': [{ recipe: 'Stew (leftover)', side_recipes: [], meal_number: 1 }],
  })

  const plan = await mealPlansApi.fetchRange('2026-08-24', '2026-08-24')

  expect(plan['2026-08-24'][0].recipe).toBe('Stew')
  expect(plan['2026-08-24'][0].leftover).toBe(true)
})
```

and put these two in its place:

```javascript
test('fetchRange takes the leftover flag from the field the server sends', async () => {
  respondWith({
    '2026-08-24': [
      { recipe: 'Stew', side_recipes: [], meal_number: 1, leftover: true },
      { recipe: 'Soup', side_recipes: [], meal_number: 2, leftover: false },
    ],
  })

  const plan = await mealPlansApi.fetchRange('2026-08-24', '2026-08-24')

  expect(plan['2026-08-24'][0].leftover).toBe(true)
  expect(plan['2026-08-24'][1].leftover).toBe(false)
})

test('fetchRange leaves a title ending in "(leftover)" alone', async () => {
  // The server sends the raw title and a separate `leftover` field
  // (crud.meal_item), so a title is never state to be parsed.
  respondWith({
    '2026-08-24': [
      { recipe: 'Stew (leftover)', side_recipes: [], meal_number: 1, leftover: false },
    ],
  })

  const plan = await mealPlansApi.fetchRange('2026-08-24', '2026-08-24')

  expect(plan['2026-08-24'][0].recipe).toBe('Stew (leftover)')
  expect(plan['2026-08-24'][0].leftover).toBe(false)
})
```

- [ ] **Step 2: Run the tests to verify the second one fails**

```bash
npm run test -- src/api/__tests__/mealPlansApi.test.js
```
Expected: `leaves a title ending in "(leftover)" alone` FAILS — `recipe` comes back as `'Stew'` and `leftover` as `true`, because the dead branch rewrites both. The other new test passes already.

- [ ] **Step 3: Remove the branch**

Replace `parseMeal` in `frontend-v2/src/api/mealPlansApi.js` (lines 3–15) with:

```javascript
// A day arrives as an array indexed by meal_number, so a slot with no meal is a
// null hole rather than a missing element. It passes straight through: parsing
// it as a meal throws, and one bad slot would blank the whole plan.
function parseMeal(meal) {
  if (!meal) return meal;
  return { ...meal, leftover: Boolean(meal.leftover) };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
npm run test -- src/api/__tests__/mealPlansApi.test.js
```
Expected: PASS.

- [ ] **Step 5: Run the whole frontend suite and the linter**

```bash
npm run test
npm run lint
```
Expected: all green. If a `MealPlanPage` test fails here it is asserting the dead suffix behaviour too — fix it to send a `leftover` field rather than restoring the parser.

- [ ] **Step 6: Commit**

```bash
git add frontend-v2/src/api/mealPlansApi.js frontend-v2/src/api/__tests__/mealPlansApi.test.js
git commit -m "Stop parsing leftover state out of the recipe title"
```

---

### Task 3: Move the backend's own tests onto `/meal-plans`

Pure refactor — no behaviour changes, and the suite must stay green throughout. This has to land **before** Task 4, or removing the routes breaks ten tests at once and the failures hide each other.

Exactly ten call sites, all `client.get("/plan", ...)` except the two multi-line ones noted below.

**Files:**
- Modify: `backend/tests/test_feedback.py:178`
- Modify: `backend/tests/test_plan_conflict_api.py:25`
- Modify: `backend/tests/test_plan_delete_api.py:74`
- Modify: `backend/tests/test_plan_range_api.py:23`
- Modify: `backend/tests/test_side_dish_api.py:33,61,152,201,228,277`

- [ ] **Step 1: Confirm the suite is green before touching anything**

Run from `backend/` (start the test database first — `docker start mp_test_pg`):
```bash
pytest -q
```
Expected: all pass. Record the count; it must not change in this task.

- [ ] **Step 2: Rewrite the single-line call sites**

In each of `tests/test_feedback.py`, `tests/test_plan_conflict_api.py` and `tests/test_side_dish_api.py`, change every occurrence of

```python
client.get("/plan", params=
```

to

```python
client.get("/meal-plans", params=
```

That is one occurrence in `test_feedback.py` (line 178), one in `test_plan_conflict_api.py` (line 25), and six in `test_side_dish_api.py` (lines 33, 61, 152, 201, 228, 277).

- [ ] **Step 3: Rewrite the two multi-line call sites**

`tests/test_plan_range_api.py:22-23` becomes:

```python
    resp = client.get(
        "/meal-plans",
```

`tests/test_plan_delete_api.py:73-74` becomes:

```python
    resp = client.delete(
        "/meal-plans",
```

- [ ] **Step 4: Verify no legacy route call sites remain, and that the `page_path` values were not touched**

```bash
grep -rn '"/plan"' tests/*.py
```
Expected: **exactly four lines**, all of them feedback metadata rather than routes —
`tests/test_user_feedback_admin.py:141`, `tests/test_user_feedback_admin.py:150`,
`tests/test_user_feedback_routes.py:61`, `tests/test_user_feedback_routes.py:66`.
If any `client.get`/`client.delete` line still appears, you missed one. If fewer than four appear, you changed a `page_path` value — revert that.

- [ ] **Step 5: Run the suite and the linter**

```bash
pytest -q
python -m flake8 .
```
Expected: the same pass count as Step 1, and flake8 clean.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/
git commit -m "Point the plan tests at /meal-plans so /plan can be retired"
```

---

### Task 4: Remove the legacy routes

Now that nothing calls `/plan`, the three stacked decorators go. The handlers themselves are untouched — they keep serving `/meal-plans`.

**Files:**
- Create: `backend/tests/test_legacy_plan_paths_removed.py`
- Modify: `backend/main.py` — the deprecation comment above `get_plan`, and one decorator on each of `get_plan`, `set_plan`, `delete_meal_plans`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_legacy_plan_paths_removed.py`:

```python
"""The legacy ``/plan`` paths are gone; ``/meal-plans`` is the only address.

``/plan/settings`` is deliberately asserted to still work: it never had a
``/meal-plans`` twin and is the current path, so a future cleanup that removes it
along with the others would be a regression.
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
    # 404, not 401: the route does not exist, so auth never gets a say.
    assert auth_client.get("/plan", params={"plan_date": "2026-01-01"}).status_code == 404
    assert auth_client.post("/plan", json={"plan": {}}).status_code == 404
    assert auth_client.delete(
        "/plan", params={"start_date": "2026-01-01", "end_date": "2026-01-01"}
    ).status_code == 404


def test_the_current_path_still_reads_a_plan(auth_client):
    resp = auth_client.get("/meal-plans", params={"plan_date": "2026-01-01"})
    assert resp.status_code == 200
```

> Both helpers already exist in `backend/tests/conftest.py`: `auth_client` (line 362) is the signed-in client fixture, used the same way as in `test_swap_api.py`, and `get_route_paths` (line 395) is the shared routing-table reader that `test_forward_compat.py` and `test_private_unreachable.py` use. Do not hand-roll either. Note `get_route_paths` returns **GET** paths only, which is why the three-verb check is the behavioural 404 test below rather than another registration assertion.

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_legacy_plan_paths_removed.py -v
```
Expected: `test_the_legacy_plan_paths_are_not_registered` and `test_the_legacy_paths_answer_404` FAIL — `/plan` is still registered and answers 200. The `/meal-plans` and `/plan/settings` tests pass already.

- [ ] **Step 3: Delete the deprecation comment and the three legacy decorators**

In `backend/main.py`, delete these three comment lines above `get_plan`:

```python
# DEPRECATED: the legacy `/plan` routes below are kept for backward
# compatibility only. Prefer the `/meal-plans` paths. Removal is scheduled no
# earlier than 2026-10-01; do not add new behaviour to the `/plan` paths.
```

Delete the legacy decorator on `get_plan`, leaving the current one:

```python
@app.get("/meal-plans", response_model=PlanOut)
def get_plan(
```

Delete the legacy decorator block on `set_plan`, leaving:

```python
@app.post(
    "/meal-plans",
    response_model=PlanOut,
)
def set_plan(
```

Delete the legacy decorator block on `delete_meal_plans`, leaving:

```python
@app.delete(
    "/meal-plans",
    response_model=Dict[str, int],
)
def delete_meal_plans(
```

Leave `plan_settings` and `update_plan_settings` and their `/plan/settings` decorators completely alone.

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/test_legacy_plan_paths_removed.py -v
```
Expected: all six PASS.

- [ ] **Step 5: Run the full suite and the linter**

```bash
pytest -q
python -m flake8 .
```
Expected: all pass, flake8 clean. A failure here means a call site was missed in Task 3 — the failing test names it.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_legacy_plan_paths_removed.py
git commit -m "Remove the legacy /plan routes"
```

---

### Task 5: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` — the "Legacy `/plan` paths" bullet under *Backend layers*

- [ ] **Step 1: Delete the bullet**

Remove this entire bullet:

```markdown
- **Legacy `/plan` paths.** Three plan routes are double-registered as stacked decorators on a single
  handler, under legacy (`/plan`) and current (`/meal-plans`) paths: `GET` (`get_plan`), `POST`
  (`set_plan`) and `DELETE` (`delete_meal_plans`). **The legacy `/plan` paths are deprecated** — do
  not add new behaviour to them. They **cannot be removed yet**:
  `frontend-v2/src/api/mealPlansApi.js` still calls all three, so migrating that file is the real
  precondition for removal, not a date. Note that `/plan/settings` (GET/PUT, `plan_settings` /
  `update_plan_settings`) is **not** legacy — it has no `/meal-plans` twin and is the current path.
```

and replace it with this one, which keeps the single fact that is still load-bearing:

```markdown
- **Plan paths.** Plan reads and writes live at `/meal-plans` (`get_plan`, `set_plan`,
  `delete_meal_plans`). `/plan/settings` (GET/PUT, `plan_settings` / `update_plan_settings`) is a
  separate, current endpoint with no `/meal-plans` twin — do not "tidy" it onto one.
```

- [ ] **Step 2: Verify no stale references survive anywhere**

```bash
grep -rn '/plan\b' CLAUDE.md README.md docs/*.md
```
Expected: only `/plan/settings` mentions remain. Anything else describing `/plan` as a plan route is now wrong and must be fixed.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "Record that /meal-plans is the only plan path"
```

---

### Task 6: Run `/simplify`

- [ ] **Step 1: Invoke the skill**

Run `/simplify` over the full diff of this plan's work. Expect it to look hardest at `parseMeal`, which Task 2 reduces to a two-line function that may now be worth inlining into its single caller, and at `test_legacy_plan_paths_removed.py`, whose six tests may collapse into fewer.

- [ ] **Step 2: Re-run both suites after any change it applies**

```bash
cd backend && pytest -q && python -m flake8 .
cd ../frontend-v2 && npm run test && npm run lint
```
Expected: all green.

- [ ] **Step 3: Commit anything it changed**

```bash
git commit -am "Simplify the /meal-plans migration"
```

---

## Deployment

**The two services must ship in this order, and this is the only risky part of the plan.**

1. Deploy **`web`** first. It now calls `/meal-plans`, which the api service already serves — so this is safe on its own and can sit in production indefinitely before step 2.
2. Confirm a real plan loads, saves and deletes in the browser.
3. Deploy **`api`**. The legacy routes disappear here.

A browser still running a cached pre-migration bundle will 404 on plan load, save and delete once step 3 lands. The alpha is small, so the practical mitigation is to do step 3 when nobody is mid-session and to hard-reload afterwards. Rolling back step 3 restores the legacy routes immediately.

No migration runs: this plan changes no models, so `alembic upgrade head` is a no-op and `seed_testing_data.py` needs no update.

---

## Self-Review

**Spec coverage.** The two decisions taken before writing: full scope including backend route removal (Tasks 3–5), and removal of the dead suffix parser (Task 2). Both covered. The frontend URL switch is Task 1, docs are Task 5, `/simplify` is Task 6 per the CLAUDE.md plan convention.

**Placeholder scan.** No TBDs. Every code step carries the actual code; every command carries its expected output. The one conditional instruction — the `auth_client` fixture name in Task 4 Step 1 — names a concrete fallback (`test_swap_api.py`) rather than leaving it open.

**Type and name consistency.** Handler names (`get_plan`, `set_plan`, `delete_meal_plans`, `plan_settings`, `update_plan_settings`) are used identically in Tasks 3, 4 and 5. `parseMeal` keeps its name and signature in Task 2. `respondWith` is the existing test helper and is reused, not redefined.

**Counts to verify while executing.** 3 frontend URLs (Task 1), 10 backend test call sites (Task 3), 3 decorators plus 1 comment block (Task 4), 4 `page_path` values that must survive untouched (Task 3 Step 4).
