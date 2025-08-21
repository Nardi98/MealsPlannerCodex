Meal Planner – MVP Spec (SI-only units, leftovers, seasonality, last-used)

Scope & Features (MVP)

Recipes (CRUD) with strict SI units.

Planner for N days, configurable meals/day, dietary filters, repeats on/off.

Last-used spacing to avoid repeats within a configurable window.

Leftover policy: cook once → eat again later in the week.

Seasonality awareness: prefer in-season dishes.

Grocery list aggregated from the plan (SI-only), CSV export.

UI to edit recipes, tweak the plan, and view/export the grocery list.

Functional Requirements

SI-only units

Allowed: mass kg, g, mg; volume L, mL; time min; temperature °C (display-only).

Canonical storage for aggregation: grams (g) and milliliters (mL).

Volume↔mass conversion via per-ingredient density.

Non-SI counts (e.g., “1 onion”) modeled via typical_item_mass_g on ingredient metadata.

Recipes

Fields: title, default servings, prep_time_min (int), bulk_preparation (bool), instructions, tags, notes.

Ingredients: (ingredient_id, qty_value, qty_unit ∈ {kg,g,mg,L,mL}, optional note).

Planner

Inputs: start date, N days, meals/day (e.g., [breakfast, lunch, dinner]), include/exclude tags, repeat policy, family size per meal, leftover rules, seasonality toggle.

Output: grid of (day × meal) with recipe or leftover assignment and per-slot servings.

Grocery list

Convert each ingredient to canonical (g/mL), aggregate by ingredient, round sensibly.

Present in kg/g and L/mL with thresholding (≥1000 g → kg, ≥1000 mL → L).

CSV export with columns: ingredient, category, amount_value, amount_unit, notes.

Seasonality

Ingredient-level seasons (months 1–12) roll up to a recipe “season score”.

Planner can prefer (soft) or require (hard) in-season ingredients per user setting.

Leftovers

From a cooked recipe, allocate leftover portions to later slots within a configurable leftover window (default 3 days).

Only recipes with bulk_preparation=True may generate leftovers; specify leftover portion counts per source cook.

Last-used spacing

Penalize or forbid recipes used within K days (user-configurable).

Non-functional Requirements

Local-first (SQLite), offline-capable.

Unit tests for conversions, aggregation, planner, and acceptance scoring.

Clear layering: DB (SQLModel) → services (planner/grocery/acceptance) → UI (Streamlit).

Performance: 14-day plan with 3 meals/day in <1s on a typical laptop.

Data Model (SQLModel / SQLite)

recipes

id PK, title (unique), servings_default int

prep_time_min int

bulk_preparation bool

instructions text, notes text nullable

created_at, updated_at

tags, recipe_tags

tags: id, name

recipe_tags: recipe_id, tag_id

ingredients

id, name (canonical), category

density_g_per_ml nullable

typical_item_mass_g nullable

season_months_json (e.g., [4,5,6,7,8])

recipe_ingredients

id, recipe_id, ingredient_id

qty_value (decimal), qty_unit enum: kg/g/mg/L/mL

note nullable

meal_plans

id, start_date, days, meals_per_day_json (e.g., ["breakfast","lunch","dinner"])

plan_items

id, plan_id, date, meal_type

recipe_id nullable (null when leftover)

servings_override int nullable

leftover_of_plan_item_id FK nullable, leftover_portions int nullable

recipe_usage (for last-used spacing)

id, recipe_id, used_on date

feedback (for acceptance learning)

id, plan_item_id, accepted bool

rating_1_5 int nullable, comments text nullable

user_profile (singleton)

dietary include/exclude tags

time budget per meal (min)

leftover window (days)

repeat_spacing_k (days)

Planning & Optimization

Acceptance model (simple, effective)

Logistic regression (L2) or SGDClassifier(loss='log_loss') predicting P(accept).

Features:

Recipe: one-hot tags, cuisine, main ingredient category, prep_time_min, bulk_preparation.

Context: meal type, day-of-week, month, family size, time-budget bucket.

History: time since last used, moving avg rating, personal acceptance rate.

Diversity: count of similar tags already scheduled this week.

Seasonality: % of ingredients in season.

Training: online updates after each plan; cold-start priors favor quick + in-season.

Output: calibrated probability p_accept per (recipe, slot).

Scheduling optimizer

Objective: maximize expected acceptance while respecting constraints.

Greedy heuristic first: per slot, choose highest score S = p_accept + bonuses - penalties, checking constraints; then apply local swaps / random restarts.

Optionally upgrade to ILP with PuLP/OR-Tools later.

Constraints

Exactly one assignment per slot: a recipe or a leftover.

Repeat spacing: if recipe on day d, forbid it for days d+1..d+K.

Leftovers: only from bulk_preparation=True recipes; leftover slots within window; respect portion counts.

Time budget: prep time per meal/day within user limit.

Dietary filters: include/exclude tags.

Seasonality: soft penalty or hard constraint per setting.

Optional bandit wrapper

Contextual bandit (Thompson Sampling or LinUCB) over the engineered features to balance exploration vs exploitation.

Grocery Aggregation (SI-only)

For each plan_item, multiplier = servings_override / servings_default.

Convert each recipe_ingredient to canonical (g or mL) using density where needed.

Sum by ingredient_id.

Display kg/g and L/mL with sensible rounding.

Export CSV.

UI Blueprint (Streamlit)

Sidebar: start date, #days, meals/day, filters, repeats toggle, leftover window, seasonality mode, time budget.

Tabs:

Planner: grid with per-cell recipe select & servings override; leftover indicators.

Recipes: list/search; edit drawer for ingredients/steps/unit validation.

Grocery List: aggregated table with category grouping + CSV export.

Settings: unit policy (read-only SI), backup/import/export.

Tech Stack

Python, SQLite, SQLModel, Alembic.

Streamlit UI.

pint (with SI whitelist) + density helpers.

scikit-learn for logistic regression (SGD online updates).

Optional PuLP for ILP.

Implementation Order

Schema & migrations (including prep_time_min, bulk_preparation, leftovers, seasonality fields).

Units layer (SI whitelist; density & typical-mass helpers).

CRUD UI for recipes/ingredients (strict SI validation).

Greedy planner with repeat spacing, leftovers, seasonality scoring hooks.

Grocery aggregation + CSV export.

Feedback capture + logistic regression scorer (persisted params).

Optional: ILP backend toggle; contextual bandit.

Acceptance Criteria

Create recipes with SI-only units, prep_time_min, bulk_preparation.

Generate a 7-day plan with 2 meals/day respecting repeat spacing, leftovers, seasonality preference.

Grocery list aggregates correctly in SI units.

Logistic regression trains on feedback and increases mean p_accept for chosen dishes over time.

Risks & Mitigations

Unit chaos → Strict SI validation; centralize conversions; warnings when density missing.

Ingredient naming drift → Typeahead from canonical ingredients; later add aliases.

Leftovers complexity → Start with simple window & portion counts; iterate after UX feedback.

