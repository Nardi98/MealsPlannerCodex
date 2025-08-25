# 🍝 Meal Planner --- Project Spec

## Core Features

1.  **Recipes management**
    -   CRUD (create, read, update, delete).
    -   Each recipe has:
        -   Title
        -   Servings default
        -   Procedure (nullable)
        -   Bulk preparation flag (leftovers possible)
        -   Ingredients (name, quantity, unit in
            `{g, kg, ml, l, piece}`)
        -   Tags (many-to-many, user-addable, e.g., *vegetarian, meat,
            pasta*)
    -   Ingredients also store their **season_months** (list of months
        1--12).
2.  **Meal plan generator**
    -   Input: start date, number of days, meals per day, bulk leftovers toggle, keep days field.
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
- **Database:** SQLite with SQLAlchemy ORM.
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
uvicorn app.main:app --reload
```

### Frontend (`frontend/`)

```bash
cd frontend
npm install
npm start
```

The React app communicates with the backend over HTTP. By default it
expects the API to be reachable at `http://localhost:8000` and sends
requests such as:

```javascript
fetch('http://localhost:8000/api/recipes')
  .then(res => res.json())
  .then(data => console.log(data))
```


## 📂 Project Structure

```
meal-planner/
│
├── README.md                  # project specs (already created)
├── backend/                   # FastAPI application
│   ├── app/                   # business logic and API routers
│   ├── requirements.txt       # backend dependencies
│   └── ...
├── frontend/                  # React application
│   ├── package.json
│   ├── src/                   # React components
│   └── ...
├── migrations/                # (optional) alembic migration scripts
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

- `DATABASE_URL` – connection string for the database
- `API_BASE_URL` – URL used by the frontend to reach the backend
- `PORT` – server port for the backend

Build steps:

- Backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Frontend: `npm run build` and serve the contents of the `build/` directory

