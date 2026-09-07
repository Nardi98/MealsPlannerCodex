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
            "Soak the stale bread in the vinegar with a splash of water.\n"
            "Roughly chop the vegetables and blend them with the garlic and "
            "salt, adding water until it is as thick as you want it.\n"
            "With the blender running, pour in the oil.\n"
            "Chill at least two hours. Do not sieve it: the fibre is the point."
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
            "Soften the chopped onion in the oil, then add the sliced "
            "courgettes and the diced potato.\n"
            "Pour in the stock, season, and simmer about twenty minutes until "
            "everything is tender.\n"
            "Take the pan off the heat, add the basil, and only then blend: "
            "off the heat the basil keeps its colour and its scent.\n"
            "Chill, and serve each bowl with a spoonful of yogurt stirred in."
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
            "Boil the farro in salted water until tender, drain, and spread it "
            "out to cool.\n"
            "Dice the aubergine, courgette and pepper, toss with a little of "
            "the oil, and roast hot until browned at the edges.\n"
            "Fold the cooled vegetables through the farro with the crumbled "
            "feta.\n"
            "Dress with the rest of the oil and the lemon juice, and tear the "
            "basil over just before serving."
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
            "Tear the stale bread into pieces and wet it briefly with water, "
            "then squeeze it dry.\n"
            "Cut the tomatoes and cucumber into chunks, slice the red onion "
            "thinly, and salt them so they give up their juice.\n"
            "Mix the bread through the vegetables and their juice with the oil "
            "and vinegar.\n"
            "Leave it half an hour for the bread to drink, and add the basil "
            "at the table."
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
            "Pour about 270 ml of boiling salted water over the couscous, "
            "cover, and leave ten minutes, then fork the grains apart.\n"
            "Dice the tomato, cucumber and pepper and slice the spring onion.\n"
            "Fold the vegetables and the drained chickpeas through the "
            "couscous.\n"
            "Dress with the lemon juice, oil and cumin, and stir in the "
            "parsley and basil."
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
            "Halve the aubergines, score the flesh, and roast them cut side "
            "down until collapsed.\n"
            "Scoop out the flesh, leaving the shells intact, and let it "
            "drain: wet flesh makes a watery filling.\n"
            "Soften the onion, add the chopped flesh, the cooked lentils, the "
            "passata, cumin and oregano, and simmer until thick.\n"
            "Fill the shells, crumble the feta over, and bake twenty minutes."
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
            "Cut the aubergine, courgette, pepper and red onion into pieces "
            "of roughly the same size.\n"
            "Toss everything with the oil, oregano and salt and spread it out "
            "in one layer; crowding steams it instead of roasting it.\n"
            "Roast hot for about thirty-five minutes, turning once.\n"
            "Add the cherry tomatoes for the last ten minutes."
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
            "Grate the courgettes, salt them, leave twenty minutes and then "
            "squeeze them hard: the water has to come out or the pastry will "
            "never crisp.\n"
            "Soften the chopped onion and mix it with the courgettes, "
            "crumbled feta, ricotta, egg, dill and pepper.\n"
            "Lay out the phyllo, brush each sheet lightly with oil, spread "
            "the filling along one edge and roll it into a coil.\n"
            "Bake about forty minutes until golden, and serve with the yogurt."
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
            "Wilt the spinach, then squeeze it dry and chop it.\n"
            "Soften the sliced spring onion and mix it with the spinach, "
            "crumbled feta, ricotta, egg, dill, nutmeg and pepper.\n"
            "Brush the phyllo sheets lightly with oil, line a dish with half "
            "of them, spread the filling, and cover with the rest.\n"
            "Score the top and bake about forty minutes; serve with the "
            "yogurt."
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
            "Roast the aubergine until soft, scoop out the flesh and let it "
            "drain before using it.\n"
            "Soften the chopped onion and pepper, then mix them with the "
            "aubergine flesh, crumbled feta, parsley and paprika.\n"
            "Cut the phyllo into strips, brush with oil, put a line of "
            "filling at one end and roll each into a cigar.\n"
            "Bake about twenty-five minutes until crisp and golden."
        ),
        "ingredients": [
            ("Phyllo Pastry", 3, "piece"),
            ("Eggplant", 500, "g"),
            ("Bell Pepper", 150, "g"),
            ("Onion", 150, "g"),
            ("Feta", 100, "g"),
            ("Parsley", 8, "g"),
            ("Paprika", 3, "g"),
            ("Olive Oil", 12, "ml"),
        ],
        "notes": [],
    },
    {
        "source": 15,
        "title": "Light Krompirusa",
        "course": "main",
        "servings": 4,
        "bulk_prep": False,
        "tags": ["vegetarian", "oven", "phyllo", "cheap"],
        "procedure": (
            "Grate the potato and the courgette, salt them, and squeeze out "
            "the water.\n"
            "Mix them with the finely sliced onion, the parmesan and plenty "
            "of black pepper.\n"
            "Brush the phyllo sheets with oil, spread the filling along them "
            "and roll each into a coil.\n"
            "Bake about fifty minutes, until the pastry is crisp and the "
            "potato is cooked through."
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
            "Slice the aubergines lengthways, brush them with a little oil "
            "and grill or roast them until pliable.\n"
            "Soften the chopped onion in the rest of the oil and simmer it "
            "with the passata into a simple sauce.\n"
            "Mix the ricotta with the parmesan, the lemon zest and the torn "
            "basil, put a spoonful on each slice and roll it up.\n"
            "Sit the rolls in the sauce and bake about twenty-five minutes."
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
            "Grate the cucumber, salt it, and squeeze it dry.\n"
            "Stir it into the yogurt with the crushed garlic and the chopped "
            "dill.\n"
            "Loosen with the oil and sharpen with the vinegar.\n"
            "Rest it an hour in the fridge before serving."
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
            "Roast the peppers whole until blackened, then close them in a "
            "bowl to steam and slip off the skins.\n"
            "Blend the flesh with the feta and the yogurt.\n"
            "Season with the paprika, the black pepper and the vinegar, and "
            "trickle in the oil.\n"
            "Chill before serving."
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
            "Warm the oil gently with the whole garlic and the rosemary to "
            "flavour it, then take out the rosemary.\n"
            "Blend the drained beans with the flavoured oil and the lemon "
            "juice, loosening with a little of their cooking water.\n"
            "Season with salt and black pepper and blend until smooth.\n"
            "Serve at room temperature."
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
            "Halve the courgettes, oil them lightly and roast them until soft "
            "and coloured.\n"
            "Blend them with the ricotta, the parmesan and the sliced spring "
            "onion.\n"
            "Season with salt and the lemon zest and juice.\n"
            "Fold in the torn basil at the end, off the heat, and chill."
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
            "Slice the courgettes into rounds, salt them and let them drain.\n"
            "Griddle or pan-fry them dry in batches until browned on both "
            "sides.\n"
            "Layer them in a dish with the sliced garlic and the basil.\n"
            "Warm the vinegar with the oil, pour it over, and leave at least "
            "a few hours before eating."
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
            "Drain and rinse the chickpeas.\n"
            "Halve the cherry tomatoes, dice the cucumber, slice the red "
            "onion thinly and stone the olives.\n"
            "Mix everything with the oregano and the parsley.\n"
            "Dress with the lemon juice and the oil and let it stand twenty "
            "minutes."
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
            "Cook the lentils in salted water until tender but whole, then "
            "drain and cool them.\n"
            "Slice the red onion thinly and halve the cherry tomatoes.\n"
            "Whisk the mustard with the vinegar and the oil into a "
            "vinaigrette.\n"
            "Toss everything together with the parsley."
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
            "Drain and rinse the beans.\n"
            "Halve the cherry tomatoes and slice the spring onion.\n"
            "Toss them with the rocket, the oil, the lemon juice and zest and "
            "the black pepper.\n"
            "Dress it at the last moment so the rocket does not wilt."
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
            "Slice the cucumbers thinly.\n"
            "Dissolve the sugar and the salt in the vinegar.\n"
            "Pour it over the cucumbers with the black pepper and the chopped "
            "dill.\n"
            "Leave at least thirty minutes in the fridge; they keep several "
            "days."
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
            "Peel the courgettes into long ribbons with a vegetable peeler.\n"
            "Dress them with the lemon juice, the oil, salt and black "
            "pepper.\n"
            "Shave the parmesan over and tear the basil on top.\n"
            "Serve straight away, while the ribbons are still crisp."
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
            "Roast the peppers whole until the skins blister, then close them "
            "in a bowl to steam and peel them.\n"
            "Tear the flesh into strips, keeping any juice that runs out.\n"
            "Dress with the sliced garlic, the capers, the vinegar, the oil "
            "and the salt.\n"
            "Scatter the parsley over and leave a couple of hours before "
            "serving."
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
            "Halve the cherry tomatoes and lay them cut side up in a dish.\n"
            "Trickle the oil over and season with the oregano and the salt.\n"
            "Bake slowly, about an hour, until shrunken and sweet.\n"
            "Keep them in the fridge under their oil."
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
