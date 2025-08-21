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
    -   Input: start date, number of days, meals per day.
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
    -   If recipe is bulk-prep, planner can generate leftover slots in
        future days.
    -   Warn if leftovers exceed "keep days".
7.  **Import/Export**
    -   Export DB to JSON.
    -   Import JSON back (overwrite/merge).

## Tech Stack

-   **Language:** Python 3.13+
-   **UI:** Streamlit (local browser interface, no backend complexity).
-   **Database:** SQLite with SQLAlchemy ORM.
-   **Frontend styling:** Streamlit widgets (no custom CSS needed).
-   **Dependencies:**\
    streamlit, SQLAlchemy, pandas, python-dateutil
-   **Version control:** Git.
-   **Deployment:** Local run with `streamlit run app.py`.


## 📂 Project Structure

```
meal-planner/
│
├── README.md                  # project specs (already created)
├── requirements.txt            # dependencies (streamlit, sqlalchemy, etc.)
├── app.py                      # entry point, streamlit main app
│
├── /mealplanner/               # application package
│   ├── __init__.py
│   ├── db.py                   # db session + engine setup
│   ├── models.py               # sqlalchemy models (recipes, ingredients, tags...)
│   ├── crud.py                 # helper functions to read/write db
│   ├── planner.py              # meal planning logic (scoring, ε-greedy, leftovers)
│   ├── scoring.py              # scoring functions (seasonality, recency, tags, bulk-prep)
│   ├── utils.py                # small helpers (date, json import/export)
│   └── seed.py                 # optional seed data for testing
│
├── /pages/                     # streamlit multipage app
│   ├── 1_Recipes.py            # CRUD for recipes, ingredients, tags
│   ├── 2_NewPlan.py            # planner setup page (inputs, sliders, filters)
│   ├── 3_PlanView.py           # view plan grid, accept/reject/swap, leftovers
│   └── 4_ImportExport.py       # json import/export
│
├── /migrations/                # (optional) alembic migration scripts
│
└── /data/
    └── app.db                  # sqlite database (created on first run)
```

## 📦 Requirements

```
streamlit
SQLAlchemy
pandas
python-dateutil
```
