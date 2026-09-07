"""The 24 summer recipes, as data.

Quantities are written for **four** portions. Where the source document gave
six, the number here is the source's times 2/3, rounded; where it gave none,
the number was chosen and is recorded in ``notes`` so the report can list it.

Nothing in this module does anything -- ``build_summer_import.py`` is what
turns it into a file. Keeping the two apart means a number can be checked by
reading it, without following any logic.
"""

# ``id`` is the ingredient's id in the account, or None for one that does not
# exist there yet. Import matches by id first and by exact name second, so a
# None here is a deliberate "create this by name"; an invented id would bind
# the line to an unrelated ingredient.
PANTRY = {
    # -- existing, referenced by id ------------------------------------------
    "Potato": {"id": 911, "season_months": [9, 10, 11, 12, 1], "grams_per_piece": None},
    "Onion": {"id": 914, "season_months": [], "grams_per_piece": 150},
    "Red Onion": {"id": 915, "season_months": [], "grams_per_piece": 120},
    "Garlic": {"id": 917, "season_months": [], "grams_per_piece": None},
    "Tomato": {"id": 919, "season_months": [6, 7, 8, 9], "grams_per_piece": 120},
    "Cherry Tomato": {"id": 920, "season_months": [6, 7, 8, 9], "grams_per_piece": 15},
    "Bell Pepper": {"id": 923, "season_months": [7, 8, 9, 10], "grams_per_piece": 150},
    "Cucumber": {"id": 925, "season_months": [6, 7, 8, 9], "grams_per_piece": 300},
    "Zucchini": {"id": 926, "season_months": [6, 7, 8, 9], "grams_per_piece": 200},
    "Eggplant": {"id": 927, "season_months": [7, 8, 9, 10], "grams_per_piece": 300},
    "Spinach": {"id": 932, "season_months": [3, 4, 5, 9, 10], "grams_per_piece": None},
    "Rocket": {"id": 935, "season_months": [5, 6, 7, 8, 9], "grams_per_piece": None},
    "Lemon": {"id": 953, "season_months": [], "grams_per_piece": 100},
    "Egg": {"id": 990, "season_months": [], "grams_per_piece": 60},
    "Greek Yogurt": {"id": 992, "season_months": [], "grams_per_piece": None},
    "Parmesan": {"id": 997, "season_months": [], "grams_per_piece": None},
    "Chickpeas": {"id": 1018, "season_months": [], "grams_per_piece": None},
    "Lentils": {"id": 1019, "season_months": [], "grams_per_piece": None},
    "Cannellini Beans": {"id": 1022, "season_months": [], "grams_per_piece": None},
    "Basil": {"id": 1025, "season_months": [5, 6, 7, 8, 9], "grams_per_piece": None},
    "Parsley": {"id": 1026, "season_months": [], "grams_per_piece": None},
    "Rosemary": {"id": 1028, "season_months": [], "grams_per_piece": None},
    "Oregano": {"id": 1030, "season_months": [], "grams_per_piece": None},
    "Cumin": {"id": 1034, "season_months": [], "grams_per_piece": None},
    "Paprika": {"id": 1035, "season_months": [], "grams_per_piece": None},
    "Nutmeg": {"id": 1037, "season_months": [], "grams_per_piece": None},
    "Black Pepper": {"id": 1039, "season_months": [], "grams_per_piece": None},
    "Salt": {"id": 1040, "season_months": [], "grams_per_piece": None},
    "Olive Oil": {"id": 1044, "season_months": [], "grams_per_piece": None},
    "White Wine Vinegar": {"id": 1048, "season_months": [], "grams_per_piece": None},
    "Passata": {"id": 1056, "season_months": [], "grams_per_piece": None},
    "Vegetable Stock": {"id": 1058, "season_months": [], "grams_per_piece": None},
    "Sugar": {"id": 1068, "season_months": [], "grams_per_piece": None},
    "Olives": {"id": 1085, "season_months": [], "grams_per_piece": None},
    # Seasonality is written, not backfilled: import assigns season_months
    # whenever the payload carries the key, so an empty list here would erase
    # what the account knows. Every existing entry repeats the account's value.
    "Capers": {"id": 1108, "season_months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
               "grams_per_piece": None},
    # -- created by this import, by name -------------------------------------
    "Feta": {"id": None, "season_months": [], "grams_per_piece": None},
    "Ricotta": {"id": None, "season_months": [], "grams_per_piece": None},
    "Phyllo Pastry": {"id": None, "season_months": [], "grams_per_piece": 40},
    "Farro": {"id": None, "season_months": [], "grams_per_piece": None},
    "Wholewheat Couscous": {"id": None, "season_months": [], "grams_per_piece": None},
    "Stale Bread": {"id": None, "season_months": [], "grams_per_piece": None},
    "Dill": {"id": None, "season_months": [5, 6, 7, 8, 9], "grams_per_piece": None},
    "Spring Onion": {"id": None, "season_months": [4, 5, 6, 7, 8, 9], "grams_per_piece": 40},
    "Dijon Mustard": {"id": None, "season_months": [], "grams_per_piece": None},
    "Red Wine Vinegar": {"id": None, "season_months": [], "grams_per_piece": None},
    # The account's "Lemon" (953) is stored as ``piece`` but holds millilitres
    # of juice. These recipes do not inherit that and do not correct it: juice
    # is its own ingredient in ml, and 953 is used only for whole fruit.
    "Lemon Juice": {"id": None, "season_months": [], "grams_per_piece": None},
}

NEW_INGREDIENTS = [name for name, e in PANTRY.items() if e["id"] is None]

# Recipes in the source document that the account already has. Importing a
# second row for one of these would split its score history and give the
# planner two candidates it cannot tell apart.
SKIPPED = [
    ("3. Hummus with crudites", "Classic Hummus (75)"),
    ("5. Baba ganoush", "Babaganoush (76)"),
    ("11. Baked courgette and onion frittata", "Zucchini Frittata (70)"),
    ("24. Tomato salad with oregano", "Tomato and Cucumber Salad (91)"),
    ("28. Green salad with lemon vinaigrette", "Green Salad (90)"),
]
