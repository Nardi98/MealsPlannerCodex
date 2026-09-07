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


# ``source`` is the recipe's number in ricettario-estivo-saziante.md.
# ``notes`` records anything the report must disclose: a quantity the source
# did not give, or one this file corrected.
RECIPES = [
    {
        "source": 1,
        "title": "Andalusian Gazpacho",
        "course": "first-course",
        "servings": 4,
        "bulk_prep": True,
        "tags": ["vegan", "no-cook", "make-ahead", "summer", "low calories"],
        "procedure": (
            "Soak the stale bread in the vinegar with a splash of water.\nRoughly chop the vegetables and blend them "
            "with the garlic and salt, adding water until it is as thick as you want it.\nWith the blender running, "
            "pour in the oil.\nChill at least two hours. Do not sieve it: the fibre is the point."
        ),
        "ingredients": [
            ("Tomato", 1000, "g"),
            ("Cucumber", 300, "g"),
            ("Bell Pepper", 150, "g"),
            ("Garlic", 5, "g"),
            ("Stale Bread", 50, "g"),
            ("Red Wine Vinegar", 30, "ml"),
            ("Olive Oil", 25, "ml"),
            ("Salt", 5, "g"),
        ],
        "notes": [
            "Cucumber and pepper given as '1 each'; taken as 300 g and 150 g.",
            "'2 tablespoons' of vinegar and oil taken as 30 ml and 25 ml.",
        ],
    },
    {
        "source": 2,
        "title": "Chilled Courgette and Basil Soup",
        "course": "first-course",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "summer", "make-ahead", "low calories"],
        "procedure": (
            "Soften the chopped onion in the oil, then add the courgettes and the potato in pieces.\nCover with the "
            "stock, season, and cook fifteen minutes.\nAdd the basil at the end of cooking, off the heat, and only "
            "then blend: off the heat it stays green and keeps its scent.\nCool it completely, and spoon the yogurt "
            "over each bowl to serve."
        ),
        "ingredients": [
            ("Zucchini", 1000, "g"),
            ("Onion", 150, "g"),
            ("Potato", 100, "g"),
            ("Vegetable Stock", 700, "ml"),
            ("Basil", 15, "g"),
            ("Olive Oil", 12, "ml"),
            ("Salt", 5, "g"),
            ("Greek Yogurt", 60, "g"),
        ],
        "notes": [],
    },
    {
        "source": 21,
        "title": "Farro Salad with Roasted Vegetables",
        "course": "first-course",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "make-ahead", "summer", "mediterranean"],
        "procedure": (
            "Dice the aubergine, courgette and pepper, dress them with a little of the oil and roast them.\nCook the "
            "farro, then cool it under running water.\nMix it with the roasted vegetables and the crumbled feta.\n"
            "Finish with the rest of the oil, the lemon zest and the basil."
        ),
        "ingredients": [
            ("Farro", 200, "g"),
            ("Eggplant", 200, "g"),
            ("Zucchini", 200, "g"),
            ("Bell Pepper", 200, "g"),
            ("Feta", 100, "g"),
            ("Basil", 5, "g"),
            ("Lemon", 0.5, "piece"),
            ("Olive Oil", 12, "ml"),
        ],
        "notes": [
            "Corrected: the source gets its roasted vegetables by pointing at "
            "'recipe 7', but recipe 7 is a bean puree and the roasting tray is "
            "recipe 10. The vegetables are listed here as ingredients of their "
            "own so the recipe stands alone.",
        ],
    },
    {
        "source": 22,
        "title": "Panzanella",
        "course": "first-course",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "no-cook", "summer", "cheap", "mediterranean"],
        "procedure": (
            "Wet the stale bread with water and vinegar, squeeze it and crumble it.\nCut the tomatoes over a bowl to "
            "catch their juice: that juice is the dressing.\nDice the cucumber and slice the red onion thinly.\nMix "
            "everything with the oil, the basil and the salt, and let it rest an hour."
        ),
        "ingredients": [
            ("Stale Bread", 150, "g"),
            ("Tomato", 800, "g"),
            ("Cucumber", 300, "g"),
            ("Red Onion", 100, "g"),
            ("Basil", 10, "g"),
            ("Olive Oil", 25, "ml"),
            ("Red Wine Vinegar", 20, "ml"),
            ("Salt", 5, "g"),
        ],
        "notes": [],
    },
    {
        "source": 23,
        "title": "Wholewheat Couscous with Chickpeas and Lemon",
        "course": "first-course",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegan", "no-cook", "make-ahead", "legumes", "high-protein"],
        "procedure": (
            "Hydrate the couscous with about 270 ml of boiling salted water, then separate the grains with a fork.\n"
            "Cut the tomato, cucumber, pepper and spring onion into small dice.\nAdd them raw, with the chickpeas, the "
            "lemon juice, the oil and the cumin.\nStir in the parsley and basil: be generous with the herbs."
        ),
        "ingredients": [
            ("Wholewheat Couscous", 180, "g"),
            ("Chickpeas", 300, "g"),
            ("Tomato", 250, "g"),
            ("Cucumber", 300, "g"),
            ("Bell Pepper", 150, "g"),
            ("Spring Onion", 40, "g"),
            ("Parsley", 10, "g"),
            ("Basil", 8, "g"),
            ("Lemon Juice", 80, "ml"),
            ("Olive Oil", 25, "ml"),
            ("Cumin", 3, "g"),
        ],
        "notes": [
            "Corrected: the source hydrates the couscous with 'an equal "
            "volume of water', which measures a weight against a volume. "
            "180 g of couscous takes about 270 ml, and that water is written "
            "into the procedure rather than listed as an ingredient.",
        ],
    },
    {
        "source": 9,
        "title": "Aubergines Stuffed with Lentils",
        "course": "main",
        "servings": 4,
        "bulk_prep": True,
        "tags": ["vegetarian", "oven", "legumes", "high-protein", "make-ahead"],
        "procedure": (
            "Halve the aubergines, score the flesh in diamonds, and bake at 200 degrees for twenty-five minutes.\n"
            "Meanwhile stew the onion in the oil, then add the cooked lentils, the passata, the cumin and the oregano "
            "and cook ten minutes.\nFill the aubergines with the lentils and scatter the crumbled feta over.\nGive "
            "them another ten minutes in the oven."
        ),
        "ingredients": [
            ("Eggplant", 1200, "g"),
            ("Lentils", 250, "g"),
            ("Onion", 150, "g"),
            ("Passata", 300, "g"),
            ("Cumin", 3, "g"),
            ("Oregano", 2, "g"),
            ("Olive Oil", 25, "ml"),
            ("Feta", 40, "g"),
        ],
        "notes": [],
    },
    {
        "source": 10,
        "title": "Tray of Roasted Summer Vegetables",
        "course": "main",
        "servings": 4,
        "bulk_prep": True,
        "tags": ["vegan", "oven", "make-ahead", "summer", "cheap"],
        "procedure": (
            "Cut the aubergine, courgette, pepper and red onion into big pieces and halve the cherry tomatoes.\nDress "
            "them with the oil, oregano and salt with your hands in a bowl: that uses far less oil than pouring it "
            "over the tray.\nSpread everything out and bake at 200 degrees for thirty minutes."
        ),
        "ingredients": [
            ("Eggplant", 400, "g"),
            ("Zucchini", 400, "g"),
            ("Bell Pepper", 300, "g"),
            ("Red Onion", 200, "g"),
            ("Cherry Tomato", 300, "g"),
            ("Olive Oil", 35, "ml"),
            ("Oregano", 3, "g"),
            ("Salt", 5, "g"),
        ],
        "notes": [
            "Chosen: the source gives no quantities here at all, only 'free "
            "quantities, fill two trays'. These weights are one tray's worth "
            "for four portions and were picked for this file.",
        ],
    },
    {
        "source": 12,
        "title": "Courgette and Feta Burek",
        "course": "main",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "oven", "phyllo", "make-ahead"],
        "procedure": (
            "Salt the grated courgettes and leave them to drain twenty minutes, then squeeze them hard with your "
            "hands: skip this and the burek comes out soggy.\nMix them with the stewed onion, the crumbled feta, the "
            "ricotta, the egg, the dill and the pepper.\nLay out a sheet of phyllo, brush it lightly with the yogurt "
            "and oil, spread filling along one side, roll it into a cigar and coil it into a round tin. Carry on with "
            "the other sheets.\nBrush the top and bake at 190 degrees for thirty-five minutes."
        ),
        "ingredients": [
            ("Phyllo Pastry", 4, "piece"),
            ("Zucchini", 533, "g"),
            ("Onion", 100, "g"),
            ("Feta", 100, "g"),
            ("Ricotta", 67, "g"),
            ("Egg", 1, "piece"),
            ("Dill", 5, "g"),
            ("Black Pepper", 2, "g"),
            ("Greek Yogurt", 45, "g"),
            ("Olive Oil", 8, "ml"),
        ],
        "notes": [
            "Corrected: the source is written for six portions, and scaling "
            "it to four gives 0.67 of an egg. Rounded up to one whole egg.",
        ],
    },
    {
        "source": 13,
        "title": "Light Spanakopita",
        "course": "main",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "oven", "phyllo", "high-protein", "make-ahead"],
        "procedure": (
            "Wilt the spinach in a pan with no added water, then drain and squeeze it thoroughly.\nMix it with the "
            "chopped spring onion, the feta, the ricotta, the egg, the dill, the nutmeg and the pepper.\nLine a tin "
            "with half the phyllo, brushed lightly with the yogurt and oil, pour in the filling and close with the "
            "rest.\nScore the portions before it goes in, and bake at 190 degrees for forty minutes."
        ),
        "ingredients": [
            ("Phyllo Pastry", 4, "piece"),
            ("Spinach", 533, "g"),
            ("Spring Onion", 100, "g"),
            ("Feta", 100, "g"),
            ("Ricotta", 100, "g"),
            ("Egg", 1, "piece"),
            ("Dill", 7, "g"),
            ("Nutmeg", 0.5, "g"),
            ("Black Pepper", 2, "g"),
            ("Greek Yogurt", 45, "g"),
            ("Olive Oil", 8, "ml"),
        ],
        "notes": [
            "Corrected: scaling the source's six portions to four gives 1.33 "
            "eggs. Rounded down to one whole egg.",
        ],
    },
    {
        "source": 14,
        "title": "Phyllo Cigars with Aubergine and Feta",
        "course": "main",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "oven", "phyllo"],
        "procedure": (
            "Bake the aubergine and pepper in cubes at 200 degrees for twenty-five minutes, with the onion.\nCrush "
            "them roughly with the feta, the parsley and the paprika.\nCut the phyllo sheets in half, put a spoonful "
            "of filling on each half, fold the sides in and roll it up tight.\nBrush them and bake at 200 degrees for "
            "twenty minutes."
        ),
        "ingredients": [
            ("Phyllo Pastry", 6, "piece"),
            ("Eggplant", 500, "g"),
            ("Bell Pepper", 150, "g"),
            ("Onion", 150, "g"),
            ("Feta", 100, "g"),
            ("Parsley", 8, "g"),
            ("Paprika", 3, "g"),
            ("Olive Oil", 12, "ml"),
        ],
        "notes": [
            "Corrected: this file first said three sheets, which would have made six cigars instead of the twelve "
            "the source's own heading promises. The source calls for six sheets cut in half. It is the one recipe "
            "here already written for four portions, so unlike the bureks it needed no scaling.",
        ],
    },
    {
        "source": 15,
        "title": "Light Krompirusa",
        "course": "main",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "oven", "phyllo", "cheap"],
        "procedure": (
            "Grate the raw potato on the coarse holes; grate the courgette and squeeze it dry.\nMix them with the "
            "chopped onion, the parmesan and plenty of black pepper. The filling goes in raw and cooks inside.\nSpread "
            "it along the phyllo sheets, roll each one up and lay them out in a spiral.\nBrush the top and bake at 190 "
            "degrees for forty-five minutes."
        ),
        "ingredients": [
            ("Phyllo Pastry", 4, "piece"),
            ("Potato", 400, "g"),
            ("Onion", 200, "g"),
            ("Zucchini", 133, "g"),
            ("Parmesan", 27, "g"),
            ("Black Pepper", 4, "g"),
            ("Olive Oil", 8, "ml"),
        ],
        "notes": [],
    },
    {
        "source": 16,
        "title": "Aubergine and Ricotta Involtini",
        "course": "main",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "oven", "high-protein", "make-ahead"],
        "procedure": (
            "Slice the aubergines lengthways and grill the slices in a pan or in the oven.\nMix the ricotta with the "
            "parmesan, the lemon zest and the basil, put a teaspoon on each slice and roll it up.\nSoften the onion in "
            "the oil and simmer it with the passata into a simple sauce.\nSit the rolls on the sauce and bake twenty "
            "minutes at 190 degrees."
        ),
        "ingredients": [
            ("Eggplant", 900, "g"),
            ("Ricotta", 250, "g"),
            ("Parmesan", 40, "g"),
            ("Lemon", 0.5, "piece"),
            ("Basil", 5, "g"),
            ("Passata", 400, "g"),
            ("Onion", 150, "g"),
            ("Olive Oil", 12, "ml"),
        ],
        "notes": [],
    },
    {
        "source": 4,
        "title": "Tzatziki",
        "course": "side",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "no-cook", "quick", "high-protein",
                 "low calories"],
        "procedure": (
            "Grate the cucumbers and wring them out in a tea towel: this is the step that decides whether it works.\n"
            "Mix them with the yogurt, the crushed garlic, the dill, the oil, the salt and a little vinegar.\nLet it "
            "rest an hour before serving."
        ),
        "ingredients": [
            ("Greek Yogurt", 330, "g"),
            ("Cucumber", 400, "g"),
            ("Garlic", 3, "g"),
            ("Dill", 7, "g"),
            ("Olive Oil", 8, "ml"),
            ("Salt", 3, "g"),
            ("Red Wine Vinegar", 7, "ml"),
        ],
        "notes": [],
    },
    {
        "source": 6,
        "title": "Roasted Pepper and Feta Cream",
        "course": "side",
        "servings": 4,
        "bulk_prep": True,
        "tags": ["vegetarian", "oven", "make-ahead", "high-protein"],
        "procedure": (
            "Roast the peppers whole at 220 degrees for thirty-five minutes.\nShut them in a covered bowl for ten "
            "minutes, then peel them: the skins come away on their own.\nBlend the flesh with the feta, the yogurt, "
            "the paprika and the vinegar.\nSeason with black pepper and finish with the oil."
        ),
        "ingredients": [
            ("Bell Pepper", 400, "g"),
            ("Feta", 100, "g"),
            ("Greek Yogurt", 67, "g"),
            ("Paprika", 3, "g"),
            ("Red Wine Vinegar", 7, "ml"),
            ("Olive Oil", 8, "ml"),
            ("Black Pepper", 1.5, "g"),
        ],
        "notes": [],
    },
    {
        "source": 7,
        "title": "Cannellini Cream with Garlic and Rosemary",
        "course": "side",
        "servings": 4,
        "bulk_prep": True,
        "tags": ["vegan", "make-ahead", "legumes", "cheap", "high-protein"],
        "procedure": (
            "Warm the oil with the garlic and the rosemary for two minutes to flavour it, then take the rosemary "
            "out.\nBlend the beans with the flavoured oil, the lemon juice and a few spoonfuls of their cooking water "
            "until smooth.\nSeason with the salt and the black pepper.\nJudge the water so it stays soft: it firms up "
            "in the fridge."
        ),
        "ingredients": [
            ("Cannellini Beans", 333, "g"),
            ("Garlic", 3, "g"),
            ("Rosemary", 2, "g"),
            ("Lemon Juice", 13, "ml"),
            ("Olive Oil", 10, "ml"),
            ("Salt", 2, "g"),
            ("Black Pepper", 1, "g"),
        ],
        "notes": [],
    },
    {
        "source": 8,
        "title": "Roasted Courgette and Ricotta Cream",
        "course": "side",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "oven", "make-ahead"],
        "procedure": (
            "Cut the courgettes into thick rounds and roast them at 220 degrees for twenty-five minutes.\nThey have to "
            "dry out and take colour; boiled, they make the cream watery.\nBlend them with the ricotta, the parmesan, "
            "the lemon zest, the spring onion and the basil.\nSeason with salt and chill."
        ),
        "ingredients": [
            ("Zucchini", 533, "g"),
            ("Spring Onion", 40, "g"),
            ("Ricotta", 100, "g"),
            ("Parmesan", 20, "g"),
            ("Lemon", 0.5, "piece"),
            ("Basil", 5, "g"),
            ("Olive Oil", 10, "ml"),
            ("Salt", 2, "g"),
        ],
        "notes": [],
    },
    {
        "source": 17,
        "title": "Courgettes in Scapece",
        "course": "side",
        "servings": 4,
        "bulk_prep": True,
        "tags": ["vegan", "make-ahead", "summer", "low calories", "cheap"],
        "procedure": (
            "Cut the courgettes into thin rounds and griddle them in a non-stick pan over a high flame, or under the "
            "oven grill.\nLayer them in a container with the sliced garlic, the basil and the salt.\nPour the vinegar "
            "and the oil over.\nLeave them to marinate at least three hours."
        ),
        "ingredients": [
            ("Zucchini", 800, "g"),
            ("Garlic", 10, "g"),
            ("White Wine Vinegar", 100, "ml"),
            ("Basil", 10, "g"),
            ("Olive Oil", 25, "ml"),
            ("Salt", 5, "g"),
        ],
        "notes": [],
    },
    {
        "source": 18,
        "title": "Mediterranean Chickpea Salad",
        "course": "side",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegan", "no-cook", "legumes", "high-protein",
                 "mediterranean"],
        "procedure": (
            "Drain the chickpeas.\nCut the cherry tomatoes, cucumber, red onion and olives into dice.\nMix everything "
            "with the oregano, the parsley, the lemon juice and the oil.\nLet it stand at least half an hour."
        ),
        "ingredients": [
            ("Chickpeas", 500, "g"),
            ("Cherry Tomato", 300, "g"),
            ("Cucumber", 300, "g"),
            ("Red Onion", 80, "g"),
            ("Olives", 60, "g"),
            ("Oregano", 2, "g"),
            ("Parsley", 8, "g"),
            ("Lemon Juice", 40, "ml"),
            ("Olive Oil", 25, "ml"),
        ],
        "notes": [],
    },
    {
        "source": 19,
        "title": "Lentil Salad with Red Onion",
        "course": "side",
        "servings": 4,
        "bulk_prep": True,
        "tags": ["vegan", "make-ahead", "legumes", "high-protein", "cheap"],
        "procedure": (
            "Slice the red onion thinly and marinate it ten minutes in the vinegar.\nEmulsify the mustard with the oil "
            "and the vinegar.\nDress the cooked lentils, the halved cherry tomatoes, the onion and plenty of parsley "
            "with it.\nRest thirty minutes before serving."
        ),
        "ingredients": [
            ("Lentils", 400, "g"),
            ("Red Onion", 100, "g"),
            ("Cherry Tomato", 300, "g"),
            ("Parsley", 10, "g"),
            ("Dijon Mustard", 12, "g"),
            ("Olive Oil", 25, "ml"),
            ("Red Wine Vinegar", 20, "ml"),
        ],
        "notes": [],
    },
    {
        "source": 20,
        "title": "Cannellini, Rocket and Cherry Tomatoes",
        "course": "side",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegan", "no-cook", "quick", "legumes", "high-protein"],
        "procedure": (
            "Crush a third of the beans lightly with a fork: it makes a cream that binds the dressing and lets you use "
            "less oil.\nHalve the cherry tomatoes and slice the spring onion.\nMix everything with the oil, the lemon "
            "zest and the black pepper.\nAdd the rocket at the last moment."
        ),
        "ingredients": [
            ("Cannellini Beans", 500, "g"),
            ("Rocket", 100, "g"),
            ("Cherry Tomato", 300, "g"),
            ("Spring Onion", 40, "g"),
            ("Lemon", 0.5, "piece"),
            ("Olive Oil", 25, "ml"),
            ("Black Pepper", 2, "g"),
        ],
        "notes": [],
    },
    {
        "source": 25,
        "title": "Quick Pickled Cucumbers",
        "course": "side",
        "servings": 4,
        "bulk_prep": True,
        "tags": ["vegan", "no-cook", "quick", "make-ahead", "low calories"],
        "procedure": (
            "Slice the cucumbers thinly.\nMix them with the vinegar, the sugar, the salt, the black pepper and the "
            "dill.\nLeave twenty minutes before serving."
        ),
        "ingredients": [
            ("Cucumber", 600, "g"),
            ("White Wine Vinegar", 45, "ml"),
            ("Sugar", 5, "g"),
            ("Salt", 3, "g"),
            ("Black Pepper", 1, "g"),
            ("Dill", 5, "g"),
        ],
        "notes": [],
    },
    {
        "source": 26,
        "title": "Raw Courgette Ribbons",
        "course": "side",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "no-cook", "quick", "summer", "low calories"],
        "procedure": (
            "Peel the courgettes into ribbons with a vegetable peeler.\nDress them with the lemon juice, the oil, the "
            "salt and the black pepper.\nAdd the shaved parmesan and the basil.\nLeave ten minutes before serving so "
            "the ribbons soften."
        ),
        "ingredients": [
            ("Zucchini", 500, "g"),
            ("Lemon Juice", 30, "ml"),
            ("Parmesan", 30, "g"),
            ("Basil", 5, "g"),
            ("Olive Oil", 10, "ml"),
            ("Salt", 3, "g"),
            ("Black Pepper", 1, "g"),
        ],
        "notes": [],
    },
    {
        "source": 27,
        "title": "Roasted Peppers in Salad",
        "course": "side",
        "servings": 4,
        "bulk_prep": True,
        "tags": ["vegan", "oven", "make-ahead", "mediterranean",
                 "low calories"],
        "procedure": (
            "Roast the peppers at 220 degrees for thirty-five minutes.\nPeel them and cut the flesh into strips.\n"
            "Dress them with the garlic in slivers, the capers, the parsley, the vinegar, the salt and a little oil."
        ),
        "ingredients": [
            ("Bell Pepper", 800, "g"),
            ("Garlic", 8, "g"),
            ("Capers", 20, "g"),
            ("Parsley", 8, "g"),
            ("Red Wine Vinegar", 15, "ml"),
            ("Olive Oil", 15, "ml"),
            ("Salt", 3, "g"),
        ],
        "notes": [
            "The account measures Capers in ml in one existing recipe and in "
            "g in another; this line uses g.",
        ],
    },
    {
        "source": 29,
        "title": "Quick Confit Cherry Tomatoes",
        "course": "side",
        "servings": 4,
        "bulk_prep": True,
        "tags": ["vegan", "oven", "make-ahead", "summer", "cheap"],
        "procedure": (
            "Halve the cherry tomatoes and lay them on baking paper.\nSeason with the salt and the oregano and trickle "
            "the oil over.\nBake at 200 degrees for twenty-five minutes, until they have concentrated and turned very "
            "sweet."
        ),
        "ingredients": [
            ("Cherry Tomato", 600, "g"),
            ("Olive Oil", 15, "ml"),
            ("Oregano", 2, "g"),
            ("Salt", 3, "g"),
        ],
        "notes": [],
    },
]
