"""Copying a shared recipe into the copier's own book (§7).

Named ``recipe_copy`` rather than ``copy``
------------------------------------------
The plan calls this module ``copy.py``. It cannot be: the backend root is
``sys.path[0]`` for both ``uvicorn main:app`` and the test suite, so a top-level
``copy.py`` shadows the standard library's ``copy`` for the entire process --
and SQLAlchemy, Pydantic, and Jinja2 all import it. Whether that breaks depends
on whether the stdlib module happened to be imported before the path entry was
added, which is exactly the kind of load-order landmine that fails in
production and not in CI. Renaming is the whole fix.

What a copy is made of
----------------------
Exactly what the share disclosed. The fields duplicated below are the PRV-2
allowlist that :mod:`public_schema` renders on the share page, and nothing
else: the copier never saw ``bulk_prep``, ``score``, or the source's planner
dates, and seeding their planner with a stranger's kitchen habits is precisely
what CP-7 is protecting against. Reading the field list as "what was shared"
rather than "every column" also means a future column on ``Recipe`` is *not*
copied until someone adds it here deliberately -- the same default-private
posture ``public_schema`` takes.

Namespace isolation (CP-3)
--------------------------
``crud.get_or_create_ingredient`` resolves by **id before name**. Every call
here passes ``ingredient_id=None`` and the copier's ``user_id``, so resolution
can only ever be "a row of mine with this name, or a new row of mine". Passing
the source's ingredient id would risk binding the copy to the source owner's
rows -- a cross-user reference CP-3 forbids and a data leak in both directions,
since editing a shared ingredient would then edit the other account's.

Transactions (CP-8)
-------------------
``crud.create_recipe`` commits internally, so it is unusable here: a copy that
commits the recipe before its ingredients exist is a partial copy, observable
by any concurrent reader. Everything below is constructed by hand and committed
exactly once, at the end.
"""

from __future__ import annotations

import hmac
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

import crud
import models

__all__ = ["copy_recipe", "is_named_recipient", "existing_copy"]


def is_named_recipient(share: models.RecipeShare, user: models.User | None) -> bool:
    """Whether ``user`` is the recipient a ``person`` share names (SH-4).

    This is the check :func:`shares.resolve` deliberately does *not* perform.
    ``resolve`` answers only "is this token live", so a caller that stops there
    turns every ``person`` share into a ``link`` share: anyone holding the URL
    would pass. Every route that honours ``mode == "person"`` must call this.

    Verification gates both arms. An unverified address must never satisfy the
    email match -- otherwise typing someone else's address at sign-up would be
    enough to read what was sent to them -- and an account whose address is
    unproven is not yet an identity this system acts on, which is the same rule
    :func:`shares.active_shares_for_recipient` applies to Shared-with-me.
    """
    if user is None or not getattr(user, "email_verified", False):
        return False
    if share.recipient_user_id is not None and share.recipient_user_id == user.id:
        return True
    named = share.recipient_email
    if named and user.email:
        return hmac.compare_digest(
            models.normalize_email(named), models.normalize_email(user.email)
        )
    return False


def existing_copy(
    session: Session, source: models.Recipe, copier: models.User
) -> models.Recipe | None:
    """The copier's earlier copy of ``source``, if they already hold one (CP-11)."""
    return session.execute(
        select(models.Recipe).where(
            models.Recipe.user_id == copier.id,
            models.Recipe.source_recipe_id == source.id,
        )
    ).scalars().first()


def _duplicate(
    session: Session, source: models.Recipe, copier: models.User
) -> models.Recipe:
    """Build one un-committed copy of ``source`` owned by ``copier``.

    Flushes (via ``crud.get_or_create_*``) but never commits, so the caller can
    build several and land them together.
    """
    author = session.get(models.User, source.user_id) if source.user_id else None

    made = models.Recipe(
        user_id=copier.id,
        title=source.title,
        servings_default=source.servings_default,
        procedure=source.procedure,
        course=source.course,
        image_url=source.image_url,
        # CP-4. Spelled out rather than left to the column defaults so the
        # requirement is visible at the point it is satisfied.
        visibility="private",
        copy_count=0,
        page_layout=None,
        # AT-1, and AT-6: the *immediate* source only. ``source.source_*`` is
        # deliberately not consulted -- lineage is one hop, never a chain.
        source_recipe_id=source.id,
        source_user_id=source.user_id,
        source_author_username=author.username if author else None,
        source_recipe_title=source.title,
        copied_at=datetime.utcnow(),
    )
    # CP-7: score, date_last_consumed, and date_last_rejected are absent above
    # and must stay absent. No planner history crosses accounts.

    for link in source.ingredients:
        ingredient = crud.get_or_create_ingredient(
            session,
            None,  # CP-3: never the source's id. See the module docstring.
            link.ingredient.name,
            link.unit or link.ingredient.unit,
            copier.id,
        )
        made.ingredients.append(
            models.RecipeIngredient(
                ingredient=ingredient, quantity=link.quantity, unit=link.unit
            )
        )

    for tag in source.tags:
        made.tags.append(crud.get_or_create_tag(session, tag.name, copier.id))

    session.add(made)
    return made


def copy_recipe(
    session: Session, source: models.Recipe, copier: models.User
) -> models.Recipe:
    """Copy ``source`` into ``copier``'s book and return the new recipe.

    Two passes (CP-6): the main recipe, then each favourite side reachable
    through the same share -- that is, each side the *source owner* owns, since
    those are the ones the share page discloses. A side belonging to anyone else
    is dropped silently rather than raising: it is a stale pairing to the
    copier, not an error.

    Raises ``PermissionError`` when the copier owns the source (CP-10). The rule
    lives here as well as at the route because a copy of one's own recipe would
    self-attribute and inflate ``copy_count``, and this layer is the one that
    would do both.
    """
    if source.user_id is not None and source.user_id == copier.id:
        raise PermissionError("Cannot copy your own recipe")

    made = _duplicate(session, source, copier)
    source.copy_count = (source.copy_count or 0) + 1  # AT-7

    if models.takes_favorite_sides(source.course):
        for side in source.favorite_sides:
            if side.user_id != source.user_id:
                continue
            side_copy = _duplicate(session, side, copier)
            side.copy_count = (side.copy_count or 0) + 1
            made.favorite_sides.append(side_copy)

    session.commit()  # CP-8: the only commit, and the whole copy is in it.
    session.refresh(made)
    return made
