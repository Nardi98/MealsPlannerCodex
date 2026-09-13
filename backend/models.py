"""SQLAlchemy models for the Meals Planner Codex application."""

from __future__ import annotations

from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    CheckConstraint,
    JSON,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
    func,
    select,
)
from sqlalchemy.orm import column_property, relationship, validates
from sqlalchemy.types import TypeDecorator

from database import Base

# Number of people a meal is cooked for when no per-user default is known.
# Shared by the model column defaults, the plan-build path, and imports so the
# fallback lives in one place.
DEFAULT_PEOPLE = 2


class IntList(TypeDecorator):
    """Store ``list[int]`` values as comma separated strings."""

    impl = String

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return ",".join(str(int(v)) for v in value)

    def process_result_value(self, value, dialect):
        if not value:
            return []
        return [int(v) for v in value.split(",") if v]


class StrList(TypeDecorator):
    """Store ``list[str]`` values as comma separated strings."""

    impl = String

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return ",".join(str(v) for v in value)

    def process_result_value(self, value, dialect):
        if not value:
            return []
        return [v for v in value.split(",") if v]


#: Canonical, ordered set of ingredient categories. Single source of truth for
#: the backend; the frontend mirrors this list in ``constants/categories.js``.
CATEGORIES: tuple[str, ...] = (
    "Vegetables",
    "Fruit",
    "Meat",
    "Fish",
    "Dairy & Eggs",
    "Grains & Pasta",
    "Legumes",
    "Herbs & Spices",
    "Condiments & Oils",
    "Nuts & Seeds",
    "Sweets & Sugar",
    "Beverages",
    "Protein",
    "Fiber",
    "Carbs",
    "Plant-based",
    "High-calorie",
)


def _owner_fk_column(*, index: bool = True) -> Column:
    """A nullable ``user_id`` FK to ``users`` for an owned resource.

    Each mapped class needs its own ``Column`` instance, so this is a factory
    rather than a shared column.

    Pass ``index=False`` where the table already declares a
    ``UniqueConstraint("user_id", ...)``: that constraint's index leads with
    ``user_id`` and already serves the ownership filter, so a standalone index
    would just be a second B-tree to maintain on every write.
    """

    return Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=index)


#: The three visibility states a recipe can hold (VIS-1). All three are defined
#: in this release; ``public`` is deliberately unreachable (VIS-5), so Part 2
#: removes a guard rather than migrating a column (FC-2).
VISIBILITY_VALUES: tuple[str, ...] = ("private", "unlisted", "public")

#: How a share grants access (SH-4). ``link`` is bearer access for anyone
#: holding the URL; ``person`` additionally requires the named recipient.
SHARE_MODES: tuple[str, ...] = ("link", "person")

#: Handles nobody may claim (UN-4). Every current and planned root route segment
#: is here -- a user called ``s`` or ``static`` would shadow the share page or
#: the public stylesheet the moment Part 2 adds ``/@{username}`` -- plus the
#: role names an impersonator would reach for.
RESERVED_USERNAMES: tuple[str, ...] = (
    # Route segments, current and planned.
    "r",
    "s",
    "api",
    "static",
    # The platform healthcheck endpoint; a handle here would shadow the probe.
    "health",
    "assets",
    "auth",
    "recipes",
    "shared",
    # UN-4 names these two literally. Neither is a claimable handle under UN-3
    # (a dot is outside the charset), but they are listed so the reserved table
    # matches the requirement rather than an interpretation of it.
    "sitemap.xml",
    "robots.txt",
    "sitemap",
    "robots",
    # Roles and reserved words.
    "admin",
    "administrator",
    "support",
    "help",
    "about",
    "login",
    "logout",
    "signup",
    "register",
    "settings",
    "account",
    "me",
    "search",
    "null",
    "undefined",
    # SYS-4: the catalog's system account. Reserving it is what stops a real
    # person from impersonating the recipe library; the account itself is
    # created below the route layer, which is the only place that checks this.
    "mealplanner",
)


def normalize_email(email: str) -> str:
    """Return the canonical stored form of ``email``: trimmed and lowercased.

    Every read and write funnels through here so stored values and lookup keys
    always match. Addresses are treated as case-insensitive in full: only the
    domain is formally case-insensitive, but no provider we target distinguishes
    the local part, and folding it whole is what users expect.
    """
    return email.strip().lower()


class User(Base):
    """An account owning its own recipes, ingredients, tags, and plans."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True, index=True)
    # The account's stable public identifier (UN-1). Non-null from the start so
    # attribution always has something to name and Part 2 can add ``/@{handle}``
    # without backfilling anyone (FC-8). ``crud.create_user`` derives one from
    # the email when the caller supplies none.
    username = Column(String, nullable=False)
    # When the handle was last chosen *by the user*. NULL therefore means
    # "system-assigned, never confirmed" (D-7), which is what forces a Google
    # sign-up through the handle-selection step in Part 1's Phase 3C.
    username_changed_at = Column(DateTime, nullable=True)
    # Null for OAuth-only accounts (e.g. Google sign-in).
    hashed_password = Column(String, nullable=True)
    display_name = Column(String)
    auth_provider = Column(String, nullable=False, default="local")
    google_sub = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    # Per-user overrides layered on top of ``DEFAULT_PLAN_SETTINGS``. ``None``
    # means "no overrides" (the account uses the shared defaults).
    plan_settings = Column(JSON, nullable=True)
    # Default number of people the shopping list scales each meal for. New
    # meals inherit this; the shopping list can override it per meal.
    default_people = Column(
        Integer, nullable=False, server_default="2", default=DEFAULT_PEOPLE
    )
    # Which system this account reads amounts in, ``metric`` or ``us``.
    # Display only: the database is always metric, and the frontend applies
    # this at render time, so toggling cannot touch stored data.
    unit_system = Column(
        String, nullable=False, server_default="metric", default="metric"
    )
    # Whether the account has proven control of its email address. Local sign-ups
    # start ``False`` and must click a verification link before they can log in;
    # Google accounts inherit the verified claim from the ID token.
    email_verified = Column(
        Boolean, nullable=False, server_default=false(), default=False
    )
    # SYS-1: marks the single account that owns the recipe catalog. Code finds
    # that account by this flag and never by its handle, email or id (SYS-6),
    # so the handle can be renamed with a one-row UPDATE.
    is_system = Column(Boolean, nullable=False, server_default=false(), default=False)
    # ADM-1 / ADM-2: granted by direct SQL only. No route, service function or
    # startup path writes it, so privilege escalation over HTTP is impossible by
    # construction rather than by a guard someone could forget.
    is_admin = Column(Boolean, nullable=False, server_default=false(), default=False)

    @validates("email")
    def _canonicalise_email(self, key: str, value: str) -> str:
        # On the model rather than in ``crud`` so that every write path obeys
        # it, including the seed scripts that construct ``User`` directly. The
        # unique index then enforces case-insensitive uniqueness by
        # construction rather than by luck of lowercase literals.
        return normalize_email(value)

    @property
    def username_confirmed(self) -> bool:
        """Whether the user, rather than the system, chose the handle (D-7).

        Derived rather than stored: §11.1 offers only ``username_changed_at``,
        and a second boolean could contradict it.
        """
        return self.username_changed_at is not None

    @validates("username")
    def _canonicalise_username(self, key: str, value: str) -> str:
        # UN-3 says input SHOULD be lowercased on entry rather than rejected for
        # case. Doing it here rather than in ``crud`` means the seed scripts and
        # any future write path get it for free.
        return value.strip().lower() if value is not None else value

    __table_args__ = (
        # UN-2: case-insensitive uniqueness enforced by the database, not by
        # application code that a second concurrent request could race past.
        # Functional index, so it is Postgres-only -- which the project already
        # is (``database.resolve_database_url`` accepts nothing else).
        Index("uq_user_username_lower", func.lower(username), unique=True),
        # SYS-2: at most one system account. Two would silently split the
        # catalog in half, so the database makes that state unrepresentable.
        # Partial, so the ``false`` every other account holds is unconstrained.
        Index(
            "uq_user_single_system",
            is_system,
            unique=True,
            postgresql_where=is_system,
        ),
    )


# Association table linking recipes and tags for a many-to-many relationship.
recipe_tag_table = Table(
    "recipe_tag",
    Base.metadata,
    Column("recipe_id", ForeignKey("recipes.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


# The sides a main dish is habitually served with. Directional (a main names its
# sides, never the reverse) and unordered: the planner picks one at random.
# Unlike ``MealSide`` -- which records what a *planned meal* actually got -- this
# is recipe-scoped and outlives any plan. ``CASCADE`` on both sides means
# deleting either recipe silently drops the pairing.
#
# No ``user_id`` here, matching ``recipe_tag_table``: both endpoints already
# carry an owner, so the column would be denormalised and could contradict them.
# The routes check that main and side share the caller's ownership.
recipe_favorite_side_table = Table(
    "recipe_favorite_sides",
    Base.metadata,
    Column(
        "main_recipe_id",
        ForeignKey("recipes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "side_recipe_id",
        ForeignKey("recipes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ``Recipe.course`` is free-text (no enum yet), so the values the domain
# actually uses are named here rather than spelled out at each call site.
SIDE_COURSE = "side"
MAIN_COURSE = "main"
# The courses the planner draws main-slot candidates from. Deliberately wider
# than ``COURSES_WITH_FAVORITE_SIDES``: a first course is planned like a main
# but is not served with a side dish.
MAIN_COURSES = (MAIN_COURSE, "first-course")
# Only a main dish is served with a side.
COURSES_WITH_FAVORITE_SIDES = (MAIN_COURSE,)


def is_side_dish(recipe: "Recipe") -> bool:
    """Whether ``recipe`` may be used as another recipe's favorite side."""
    return recipe.course == SIDE_COURSE


def takes_favorite_sides(course: str) -> bool:
    """Whether ``course`` is served with a side dish."""
    return course in COURSES_WITH_FAVORITE_SIDES


class UnitEnum(str, PyEnum):
    """The units a quantity may be *stored* in: one base unit per dimension.

    ``kg`` and ``l`` are deliberately absent. They are ways of writing a stored
    amount down -- formatting, on the same footing as ``cup`` or ``oz`` -- and
    the frontend's ``utils/units.js`` owns that translation at the edges. A
    narrow storage vocabulary is what makes aggregating two recipes well
    defined; the wide vocabulary never reaches the database.
    """

    G = "g"
    ML = "ml"
    PIECE = "piece"


class DimensionEnum(str, PyEnum):
    """What a quantity measures: weigh it, measure it, or count it.

    A *dimension*, not a unit, on purpose. Whether mass reads as ``g``, ``kg``
    or ``oz`` is already decided by the account's metric/US setting, so storing
    a unit here would encode the same choice twice and permit the two to
    contradict each other.
    """

    MASS = "mass"
    VOLUME = "volume"
    PIECE = "piece"


class Recipe(Base):
    """A meal that can be prepared and consumed.

    Ingredient quantities are stored **exactly as authored**, for the number of
    people in :attr:`servings`. Nothing rewrites them: everything that renders
    them scales by ``target / servings`` -- the shopping list by ``Meal.people``,
    the public share page by its ``?servings=`` control. Recipes predating this
    column were written per person and so carry ``servings = 1``.
    """

    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    user_id = _owner_fk_column()
    title = Column(String, nullable=False)
    procedure = Column(Text)
    bulk_prep = Column(Boolean, default=False)
    score = Column(Float)
    date_last_consumed = Column(Date)
    date_last_rejected = Column(Date)
    course = Column(String, nullable=False, default="main")
    image_url = Column(String, nullable=True)
    # How many people the ingredient quantities above were written for. Never a
    # scaling factor applied to storage -- only readers divide by it.
    servings = Column(Integer, nullable=False, server_default="1", default=1)

    # --- Sharing (Part 1) ------------------------------------------------
    # VIS-2: private at the *database* level, so a row created by any path --
    # import, seed script, raw SQL -- is private unless it says otherwise.
    visibility = Column(
        String, nullable=False, server_default="private", default="private"
    )
    # FC-3 / FC-4: always NULL in this release. ``page_layout is None`` means
    # "render the default block list"; Part 2's editor writes them without a
    # schema change.
    page_layout = Column(JSON, nullable=True)
    page_theme = Column(JSON, nullable=True)
    # AT-7: shown to the owner as "copied N times". Copier identities are never
    # stored, so this counter is the whole of what the owner can learn.
    copy_count = Column(Integer, nullable=False, server_default="0", default=0)

    # --- Attribution snapshot (AT-1) -------------------------------------
    # The two FKs are ``ON DELETE SET NULL`` and the two text columns are
    # snapshots: deleting the source recipe or the source account must not erase
    # the credit (AT-2). Only the immediate source is recorded (AT-6).
    # Indexed (DM-5): a catalog listing groups copies by their source to count
    # adopters, which is otherwise a sequential scan of every recipe.
    source_recipe_id = Column(
        Integer,
        ForeignKey("recipes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # API-16: a copy whose source account is the system account came from the
    # recipe library. Derived in SQL rather than stored, so it cannot drift from
    # the snapshot and ``Recipe`` gains no column (DM-7). ``coalesce`` covers a
    # copy whose source account was deleted (``source_user_id`` SET NULL).
    from_library = column_property(
        func.coalesce(
            select(User.is_system)
            .where(User.id == source_user_id)
            .correlate_except(User)
            .scalar_subquery(),
            false(),
        )
    )
    source_author_username = Column(String, nullable=True)
    source_recipe_title = Column(String, nullable=True)
    copied_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "visibility IN ('private', 'unlisted', 'public')",
            name="ck_recipe_visibility",
        ),
        CheckConstraint("servings >= 1", name="ck_recipe_servings_positive"),
    )

    # Relationship to ``RecipeIngredient`` association objects.
    ingredients = relationship(
        "RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan"
    )
    tags = relationship(
        "Tag", secondary=recipe_tag_table, back_populates="recipes"
    )
    favorite_sides = relationship(
        "Recipe",
        secondary=recipe_favorite_side_table,
        primaryjoin=id == recipe_favorite_side_table.c.main_recipe_id,
        secondaryjoin=id == recipe_favorite_side_table.c.side_recipe_id,
    )
    # DM-10. ``passive_deletes`` leaves removal to the table's ``ON DELETE
    # CASCADE`` instead of having the ORM load the entry just to delete it.
    catalog_entry = relationship(
        "CatalogEntry",
        back_populates="recipe",
        uselist=False,
        passive_deletes=True,
    )

    @property
    def favorite_side_ids(self) -> list[int]:
        """The favorite sides flattened to ids, as the API exposes them."""
        return [side.id for side in self.favorite_sides]


class CatalogEntry(Base):
    """A recipe's membership of the recipe catalog (spec §5).

    Curation is kept apart from authorship: a recipe is in the catalog exactly
    when it has a ``published`` row here (P2-1), whoever owns it. That is what
    lets a user-published recipe join later by inserting one row (FC-1).

    ``recipe_id`` is the primary key (DM-2) because a recipe is catalogued at
    most once, and there is deliberately no ``user_id`` (DM-8): the owner is
    reachable through the recipe, and a copy of it here could contradict it.
    """

    __tablename__ = "catalog_entries"

    recipe_id = Column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    status = Column(
        String, nullable=False, server_default="published", default="published"
    )
    published_at = Column(DateTime, nullable=False, server_default=func.now())
    retired_at = Column(DateTime, nullable=True)

    recipe = relationship("Recipe", back_populates="catalog_entry")

    __table_args__ = (
        # Both named (MIG-2): an unnamed CHECK has nothing in the metadata to
        # match the reflected one against -- see ``meals_meal_number_check``.
        CheckConstraint(
            "status IN ('published', 'retired')", name="ck_catalog_entry_status"
        ),
        # DM-4, the same all-or-nothing shape as
        # ``ck_meal_leftover_source_all_or_nothing``.
        CheckConstraint(
            "(status = 'retired') = (retired_at IS NOT NULL)",
            name="ck_catalog_entry_retired_all_or_nothing",
        ),
    )


class Ingredient(Base):
    """A unique ingredient that can appear in many recipes."""

    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True)
    # uq_ingredient_user_name already indexes (user_id, name).
    user_id = _owner_fk_column(index=False)
    name = Column(String, nullable=False)
    season_months = Column(IntList)
    categories = Column(StrList, nullable=True)
    # The two numbers that let a reader cross a dimension: a density and the
    # weight of one of them. NULL is a *recorded fact* -- pieces of milk is a
    # category error, not absent data -- so the converter refuses to cross a
    # NULL rather than inventing a factor, water's density included.
    grams_per_ml = Column(Float, nullable=True)
    grams_per_piece = Column(Float, nullable=True)
    # Which dimension leads when this ingredient is displayed. NULL falls back
    # to whichever dimension most of the contributing recipes used. Display
    # only: it never rewrites a stored quantity.
    preferred_dimension = Column(
        Enum(DimensionEnum, name="dimension_enum"), nullable=True
    )

    recipes = relationship(
        "RecipeIngredient", back_populates="ingredient", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_ingredient_user_name"),
    )


class RecipeIngredient(Base):
    """Association table linking recipes and ingredients with quantities."""

    __tablename__ = "recipe_ingredients"

    recipe_id = Column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id = Column(
        Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), primary_key=True
    )
    quantity = Column(Float)
    unit = Column(Enum(UnitEnum, name="unit_enum"))

    recipe = relationship("Recipe", back_populates="ingredients")
    ingredient = relationship("Ingredient", back_populates="recipes")

    # Convenience accessors so Pydantic schemas can read attributes directly
    @property
    def id(self) -> int:  # pragma: no cover - simple delegation
        return self.ingredient_id

    @property
    def name(self) -> str:  # pragma: no cover - simple delegation
        return self.ingredient.name

    @property
    def season_months(self) -> list[int] | None:  # pragma: no cover
        return self.ingredient.season_months

    # The line's own unit is authoritative, but restating it in another
    # dimension needs the ingredient's physics, so a reader gets both at once.
    @property
    def grams_per_ml(self) -> float | None:  # pragma: no cover
        return self.ingredient.grams_per_ml

    @property
    def grams_per_piece(self) -> float | None:  # pragma: no cover
        return self.ingredient.grams_per_piece

    @property
    def preferred_dimension(self) -> DimensionEnum | None:  # pragma: no cover
        return self.ingredient.preferred_dimension


class Tag(Base):
    """A simple label that can be attached to recipes."""

    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    # uq_tag_user_name already indexes (user_id, name).
    user_id = _owner_fk_column(index=False)
    name = Column(String, nullable=False)
    penalize_repetition = Column(Boolean, nullable=False, server_default=false())
    is_system = Column(Boolean, nullable=False, server_default=false())

    recipes = relationship(
        "Recipe", secondary=recipe_tag_table, back_populates="tags"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_tag_user_name"),
    )


class MealPlan(Base):
    """A dated collection of planned meals."""

    __tablename__ = "meal_plans"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_date = Column(Date, nullable=False)

    meals = relationship(
        "Meal",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="Meal.meal_number",
    )

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "plan_date"),
    )


class Meal(Base):
    """A specific meal within a :class:`MealPlan`."""

    __tablename__ = "meals"

    user_id = Column(Integer, nullable=False)
    plan_date = Column(Date, nullable=False)
    meal_number = Column(Integer, nullable=False)
    # CASCADE, not SET NULL: a meal *is* its recipe, so deleting the recipe
    # must take the row with it. SET NULL left a ghost row the read path
    # skipped while its ``meal_number`` still occupied the day, which is how a
    # deleted lunch used to break the whole plan.
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"))
    accepted = Column(Boolean, default=False)
    # Number of people this meal is cooked for. The shopping list scales the
    # recipe's (and its sides') ingredient amounts by ``people /
    # Recipe.servings`` -- this is the numerator, the recipe's authored basis
    # the denominator. Sides scale with their parent meal, so they carry no
    # people column of their own.
    people = Column(
        Integer, nullable=False, server_default="2", default=DEFAULT_PEOPLE
    )
    # A meal is a leftover iff it links back to the source meal that produced
    # it. The two columns are all-or-nothing (see the CHECK constraint below);
    # ``leftover`` is derived from their presence rather than stored separately.
    leftover_source_date = Column(Date, nullable=True)
    leftover_source_meal = Column(Integer, nullable=True)

    plan = relationship("MealPlan", back_populates="meals")
    recipe = relationship("Recipe", foreign_keys=[recipe_id])
    sides = relationship(
        "MealSide",
        back_populates="meal",
        cascade="all, delete-orphan",
        order_by="MealSide.position",
    )

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "plan_date", "meal_number"),
        ForeignKeyConstraint(
            ["user_id", "plan_date"],
            ["meal_plans.user_id", "meal_plans.plan_date"],
            ondelete="CASCADE",
        ),
        # Named explicitly, with the exact name PostgreSQL was already deriving
        # for it. An unnamed constraint has no name in the metadata to match
        # the reflected one against, so autogenerate reads it as "present in
        # the database, absent from the models" and proposes dropping it on
        # every single migration. Naming it is not a schema change.
        CheckConstraint("meal_number IN (1,2)", name="meals_meal_number_check"),
        CheckConstraint(
            "(leftover_source_date IS NULL) = (leftover_source_meal IS NULL)",
            name="ck_meal_leftover_source_all_or_nothing",
        ),
    )

    @property
    def leftover(self) -> bool:
        """A meal is a leftover exactly when it links to a source meal."""
        return self.leftover_source_date is not None

    @property
    def side_recipe(self):
        return self.sides[0].side_recipe if self.sides else None

    @property
    def side_recipe_id(self):
        return self.sides[0].side_recipe_id if self.sides else None


class RefreshToken(Base):
    """A server-side record of an issued refresh token.

    The token itself is a signed JWT held only in the client's ``HttpOnly``
    cookie; this table stores its ``jti`` so a token can be revoked (on logout,
    rotation, or password reset) independently of its cryptographic expiry. A
    refresh presented whose ``jti`` is missing, ``revoked``, or past
    ``expires_at`` is rejected.
    """

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jti = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, nullable=False, server_default=false(), default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class RecipeShare(Base):
    """One secret-token grant of read access to one recipe (§11.3).

    The raw token exists only in the URL the sharer forwards: this row stores a
    SHA-256 digest of it (SH-3), so read access to the database yields no usable
    share URL. ``__repr__`` is overridden so the digest cannot leak into a log
    line either.

    Validity is *not* modelled as a column. ``revoked_at`` and ``expires_at``
    are read after the row is fetched (D-5), which is what keeps token lookup
    constant-time with respect to validity (SH-27).
    """

    __tablename__ = "recipe_shares"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer,
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256 hex digest. Unique and indexed so resolution is a single equality
    # lookup rather than the O(n) scan a password hash would force.
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    mode = Column(String, nullable=False)
    # Either may be set for a ``person`` share; a ``link`` share may carry a
    # recipient purely so the recipe lands in their Shared-with-me (SH-6).
    recipient_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    recipient_email = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    # SH-26: the only view telemetry kept. No per-visit log, no visitor
    # identity, no IP address.
    last_viewed_at = Column(DateTime, nullable=True)
    dismissed_by_recipient_at = Column(DateTime, nullable=True)

    recipe = relationship("Recipe")

    __table_args__ = (
        CheckConstraint(
            "mode <> 'person' OR recipient_user_id IS NOT NULL "
            "OR recipient_email IS NOT NULL",
            name="ck_share_person_requires_recipient",
        ),
        CheckConstraint(
            "mode IN ('link', 'person')", name="ck_share_mode"
        ),
        Index("ix_recipe_shares_recipient_user", "recipient_user_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        # Deliberately omits ``token_hash``: a digest in a traceback or a log
        # aggregator is a standing offline-guessing target for no benefit.
        return f"<RecipeShare id={self.id} recipe_id={self.recipe_id} mode={self.mode!r}>"


class ReservedUsername(Base):
    """A handle nobody may claim, permanently or for a window (§11.3).

    ``reason='system'`` covers the UN-4 list and is permanent
    (``reserved_until IS NULL``). ``reason='released'`` is UN-9's cooling-off
    period after a user changes handle: the column ships now so the Part 2 flow
    needs no migration.
    """

    __tablename__ = "reserved_usernames"

    username = Column(String, primary_key=True)
    reason = Column(String, nullable=False, server_default="system")
    reserved_until = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "reason IN ('system', 'released')", name="ck_reserved_username_reason"
        ),
    )


class MealSide(Base):
    """Side dishes associated with a :class:`Meal`."""

    __tablename__ = "meal_side_dishes"

    user_id = Column(Integer, nullable=False)
    plan_date = Column(Date, nullable=False)
    meal_number = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False)
    # Deleting a recipe is a user-facing action that must not be blocked by a
    # plan referencing it: the side simply drops off the meal. CASCADE rather
    # than SET NULL because a side row with no recipe has nothing to say.
    # Note this leaves a gap in ``position`` -- see ``crud.add_meal_side``.
    side_recipe_id = Column(
        Integer,
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
    )

    meal = relationship("Meal", back_populates="sides")
    side_recipe = relationship("Recipe")

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "plan_date", "meal_number", "position"),
        ForeignKeyConstraint(
            ["user_id", "plan_date", "meal_number"],
            ["meals.user_id", "meals.plan_date", "meals.meal_number"],
            ondelete="CASCADE",
        ),
    )
