# 🍝 Meal Planner --- Project Spec

## Core Features

1.  **Recipes management**
    -   CRUD (create, read, update, delete).
    -   Each recipe has:
        -   Title
        -   Servings default
        -   Procedure (nullable)
        -   Bulk preparation flag (leftovers possible)
        -   Course (main, side, first-course)
        -   Ingredients (name, quantity, unit in
            `{g, kg, ml, l, piece}`)
        -   Tags (many-to-many, user-addable, e.g., *vegetarian, meat,
            pasta*)
    -   Ingredients also store their **season_months** (list of months
        1--12).
2.  **Meal plan generator**
    -   Input: start date, end date, meals per day, bulk leftovers toggle, keep days field.
    -   For each slot, propose a recipe using a **scoring function**:
        -   Base preference score (per-recipe, updated on
            accept/reject).
        -   Seasonality (all ingredients in season → bonus, else
            penalty).
        -   Recency penalty (recently eaten recipes are down-weighted).
        -   Tag penalties (avoid = exclude, reduce = down-weight).
        -   Bulk-prep bonus when leftovers are useful.
    -   **Exploration vs exploitation** via ε-greedy (user controls ε).
    -   Leftovers automatically placed within a "keep days" window.
    -   User can accept, reject, or swap each slot.
3.  **Learning**
    -   Recipes have `score` and `date_last_consumed` stored directly in
        the DB.
    -   Accept → `score += +1`, update `date_last_consumed`.
    -   Reject → `score += -1`.
    -   Sliders allow adjusting weights (seasonality, recency, tags,
        bulk-prep).
4.  **Seasonality**
    -   Calculated per recipe by checking all ingredients.
    -   Soft scoring: fraction of in-season ingredients.
5.  **Tags**
    -   Many-to-many between recipes and tags.
    -   Filter mode:
        -   **Avoid**: recipes with selected tags are excluded.
        -   **Reduce**: recipes with selected tags are penalized.
6.  **Leftover management**
    -   Toggle bulk leftovers on or off and define how many "keep days" they remain.
    -   If recipe is bulk-prep, planner can generate leftover slots in
        future days.
    -   Warn if leftovers exceed "keep days".
7.  **Import/Export**
    -   Export DB to JSON.
    -   Import JSON back (overwrite/merge).

## Tech Stack

- **Backend:** Python 3.13+ with FastAPI served via `uvicorn`.
- **Frontend:** React.
- **Database:** PostgreSQL with SQLAlchemy ORM (falls back to a local SQLite file when `DATABASE_URL` is unset).
- **Version control:** Git.

### UI

## Color palette 
- white F8FAF9
- positive colour 0c3a2d
- negative colour bd210f
- other colours 6d9773 FFB902 BB8A52

## Development Setup

### Backend (`backend/`)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

#### Database schema & migrations

The schema is created automatically on startup: `main.py` calls
`Base.metadata.create_all`, so a **fresh** database needs no migration step. During
development this is the whole story — to change the schema, change the SQLAlchemy
model and start against a fresh DB.

There is **no active migration system**. Real migrations will be introduced with
`alembic init` when the project approaches production and needs to evolve a populated
database in place. A historical changelog of past schema changes is kept in
[`backend/migrations/README.md`](backend/migrations/README.md).

### Frontend (`frontend-v2/`)

The repository includes an updated UI located in `frontend-v2/`. Start it with
`docker-compose up frontend-v2` and access it at
[`http://localhost:3000`](http://localhost:3000).


## 📂 Project Structure

```
meal-planner/
│
├── README.md                  # project specs (already created)
├── backend/                   # FastAPI application
│   ├── app/                   # business logic and API routers
│   ├── requirements.txt       # backend dependencies
│   └── ...
├── frontend-v2/             # Updated UI
│   ├── package.json
│   ├── src/                   # React components
│   └── ...
├── migrations/                # schema-change changelog (no active migrations)
└── data/
    └── app.db                 # sqlite database (created on first run)
```

## 📦 Requirements

### Backend

```
fastapi
uvicorn
SQLAlchemy
pandas
python-dateutil
```

### Frontend

```
Node.js
npm
React
```

## Deployment

Use Docker Compose to build and run both services:

```bash
docker-compose up --build
```

Set the necessary environment variables before starting:

- `DATABASE_URL` – SQLAlchemy connection string for the database. Set to a
  PostgreSQL URL (e.g. `postgresql://user:pass@host:5432/mealsdb`); Railway
  injects this automatically. A bare `postgres://` scheme is normalized to
  `postgresql://`. When unset, the backend falls back to a local SQLite file at
  `data/app.db`.
- `API_BASE_URL` – URL used by the frontend to reach the backend
- `PORT` – server port for the backend
- `JWT_SECRET` – signing key for the auth tokens (a dev-only default is used
  when unset — always set this in production)
- `GOOGLE_CLIENT_ID` – Google OAuth client ID, required by the backend to
  verify ID tokens for "Sign in with Google"
- `VITE_GOOGLE_CLIENT_ID` – the *same* client ID, given to the frontend at
  build time so it can render the Google button. Without it the login page
  offers email/password only.

### Setting up "Sign in with Google"

1. In the [Google Cloud console](https://console.cloud.google.com/apis/credentials),
   create an **OAuth 2.0 Client ID** of type *Web application*.
2. Add your app's origin (e.g. `http://localhost:3000`) to **Authorized
   JavaScript origins**.
3. Set `GOOGLE_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (frontend) to
   the generated client ID. Under Docker Compose, setting `GOOGLE_CLIENT_ID`
   alone is enough — compose passes it through to both services. The client
   *secret* is not needed: the browser obtains the ID token and the backend
   only verifies it.

Build steps:

- Backend: `uvicorn main:app --host 0.0.0.0 --port 8000`
- Frontend: `npm run build` and serve the contents of the `build/` directory

## Database Schema

The planner persists generated meals using two tables:

* `meal_plans` – one row per day with the unique column `plan_date`.
* `meals` – individual meal slots linked to a plan.

The `meals` table has the following columns:

| Column      | Type   | Notes |
|-------------|--------|-------|
| `plan_date` | DATE   | FK to `meal_plans.plan_date` |
| `meal_number` | INTEGER | Meal slot within the day (1 or 2) |
| `recipe_id` | INTEGER | FK to `recipes.id` |
| `accepted`  | BOOLEAN | Whether the user accepted the suggestion |

The primary key is the composite `(plan_date, meal_number)` and a check
constraint restricts `meal_number` to `1` or `2`.

## Meal Plan API

### Generating a plan

`POST /meal-plans/generate` creates a temporary plan without saving it. The
payload controls the date range to generate and how many meals per day:

```json
{
  "start": "2024-01-01",
  "end": "2024-01-02",
  "meals_per_day": 2,
  "keep_days": 3,
  "bulk_leftovers": true
}
```

The response maps dates to recipe suggestions, each including the recipe
`id` and `title`:

```json
{
  "2024-01-01": [{"id": 1, "title": "Soup"}],
  "2024-01-02": [{"id": 2, "title": "Stew"}]
}
```

### Retrieving a plan

`GET /meal-plans` returns a mapping of ISO dates to their meals, each including
an `accepted` flag:

```json
{
  "2024-01-01": [
    {"recipe": "Soup", "accepted": false},
    {"recipe": "Salad", "accepted": true}
  ]
}
```

### Setting a plan and overwrite confirmation

Plans are saved with `POST /meal-plans`. The payload uses a daily plan
model mapping dates to recipe IDs:

```json
{
  "plan_date": "2024-01-01",
  "plan": {"2024-01-01": [1, 2]},
  "bulk_leftovers": true,
  "keep_days": 3
}
```

If any of the supplied `plan_date` values already exist, the API returns
`409` with a `conflicts` array. Resubmit the request with
`?force=true` to overwrite existing plans.

### Toggling meal acceptance

Use `POST /meal-plans/accept` to update the `accepted` flag for a meal:

```json
{
  "plan_date": "2024-01-01",
  "meal_number": 1,
  "accepted": true
}
```

The updated meal is returned in the response.



## Next-gen UI

To spin up the experimental Vite interface:

```bash
cd frontend-v2
npm install
npm run dev
```

All UI updates must adhere to [MEAL_PLANNER_DESIGN_GUIDE.md](MEAL_PLANNER_DESIGN_GUIDE.md) and the project mock-up. Non-Recipe pages are currently placeholders, and their sidebar buttons are disabled until future tasks.

