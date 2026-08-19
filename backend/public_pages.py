"""The unauthenticated share page at ``/s/{token}`` (§3, §6).

Phase 0 shipped this module empty and pre-wired into ``main`` (D-6); Phase 2B
fills it in.

This is the product's *only* unauthenticated surface, so the requirements it
carries are disproportionate to its size: server-rendered complete HTML that is
fully readable with JavaScript disabled (RA-1/RA-2), a byte-identical neutral
404 for revoked, expired, and nonexistent tokens alike (SH-22), no
``Set-Cookie`` of any kind (PRV-6), ``noindex`` plus ``Referrer-Policy:
no-referrer`` (RA-8, SH-28), and output serialised through the PRV-1 allowlist
rather than the ORM model.

Two things here deserve a note before anyone edits them.

**Person-mode access control lives in this route, not in ``shares.resolve``.**
``resolve`` deliberately answers only "is this token live" so that its cost --
and therefore its timing -- does not depend on who is asking (SH-27). That
leaves SH-23/SH-24 to the caller, and this is the caller. A ``person`` share is
*not* a bearer capability: holding the URL is necessary but not sufficient, and
the sufficient part is being signed in as an account whose **verified** email
(or account id) matches the named recipient. Unverified never matches -- an
unproven address would otherwise let anyone who can type someone else's email
read what was sent to them.

**The page has no JavaScript at all.** SP-2's servings control is a plain
``<form method="get">`` re-rendered on the server. Please do not "upgrade" it
with an inline script: ``script-src 'none'`` below, the template's own tests,
and RA-2 all depend on that staying true.
"""
from __future__ import annotations

import os
from datetime import datetime
from urllib.parse import quote, urljoin

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import auth_users
import blocks as public_blocks
import models
import public_copy
import public_markup
import shares
from database import get_db
from public_schema import PublicRecipe

router = APIRouter(tags=["public"])

#: Headers every response from this router carries, whatever its status.
#:
#: ``Referrer-Policy`` is set as a *header* and not only as the template's meta
#: tag: the share token is in the URL, so a leaking ``Referer`` hands the
#: capability to whatever third party the visitor clicks through to, and a meta
#: tag is only honoured by clients that parse the document. ``X-Robots-Tag``
#: doubles the ``noindex`` meta for the same reason (RA-8). ``Vary`` is there so
#: no cache or link unfurler serves an Italian page to an English reader (D-9),
#: and the CSP is a second line of defence behind ``public_markup``: the page
#: has no inline script and no off-origin subresource, so it costs nothing.
PAGE_HEADERS = {
    "Cache-Control": "private, no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
    "Vary": "Accept-Language",
    "Content-Security-Policy": "default-src 'self'; script-src 'none'",
}

#: SH-22: one body, one status, for revoked, expired and never-existed alike.
#: A constant rather than an ``HTTPException`` so the bytes cannot drift apart
#: between call sites.
_NOT_FOUND_BODY = "Not Found"


def _frontend_url() -> str:
    """``FRONTEND_URL``, read from the environment rather than from ``main``.

    ``main`` imports this router, so importing ``main`` back would close a
    cycle. Read per call so tests (and a reconfigured process) see the current
    value.
    """
    return os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")


def optional_current_user(
    request: Request, db: Session = Depends(get_db)
) -> models.User | None:
    """The signed-in user, or ``None``.

    ``auth_users.get_current_user`` is strict by design (401 when absent), and
    this page must render for a visitor with no account at all. The bearer token
    is read off the request directly rather than through ``OAuth2PasswordBearer``
    so that an override of the strict dependency in a test cannot silently
    change who this page thinks is calling.
    """
    scheme, token = get_authorization_scheme_param(
        request.headers.get("Authorization", "")
    )
    if not token or scheme.lower() != "bearer":
        return None
    subject = auth_users.decode_token(token)
    if subject is None:
        return None
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        return None
    return db.get(models.User, user_id)


def mask_email(address: str | None) -> str:
    """Mask an address for the SH-24 refusal: ``a********o@example.org``.

    The refusal has to say *something* -- "this link is for a different
    account" is useless if the reader cannot tell which of their accounts to
    use -- while not disclosing an address to whoever holds the URL. Keeping
    only the first and last characters of the local part is the smallest hint
    that achieves that; a local part shorter than three characters is masked
    whole, since first-and-last would be the entire thing. A string with no
    ``@`` is not an address we recognise, so it is masked entirely.
    """
    if not address:
        return ""
    local, sep, domain = address.partition("@")
    if not sep:
        return "*" * len(address)
    if len(local) <= 2:
        return f"{'*' * len(local)}@{domain}"
    return f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}@{domain}"


def _with_headers(response):
    for key, value in PAGE_HEADERS.items():
        response.headers[key] = value
    return response


def _not_found() -> PlainTextResponse:
    return _with_headers(
        PlainTextResponse(_NOT_FOUND_BODY, status_code=404)
    )


def _is_named_recipient(share: models.RecipeShare, user: models.User) -> bool:
    """Whether ``user`` is the account a ``person`` share was addressed to.

    Verification gates *both* match arms, including the account-id one: an
    account that has not proved its address is not yet an identity this product
    acts on (the same rule ``shares.active_shares_for_recipient`` applies to
    Shared-with-me, SWM-4).
    """
    if not getattr(user, "email_verified", False):
        return False
    if share.recipient_user_id is not None and share.recipient_user_id == user.id:
        return True
    if share.recipient_email and user.email:
        return models.normalize_email(user.email) == share.recipient_email
    return False


def _recipient_hint(db: Session, share: models.RecipeShare) -> str:
    """The masked address to name in an SH-24 refusal."""
    if share.recipient_email:
        return mask_email(share.recipient_email)
    if share.recipient_user_id is not None:
        recipient = db.get(models.User, share.recipient_user_id)
        if recipient is not None:
            return mask_email(recipient.email)
    return ""


def _load_recipe(db: Session, recipe_id: int):
    """Load the recipe and its author in one round trip (NF-2).

    Everything the page renders is eager-loaded here, so rendering itself
    issues no further queries: a lazy load per ingredient is the difference
    between NF-1's 300 ms budget and missing it on a long recipe.
    """
    return db.execute(
        select(models.Recipe, models.User)
        .join(models.User, models.User.id == models.Recipe.user_id)
        .where(models.Recipe.id == recipe_id)
        .options(
            selectinload(models.Recipe.tags),
            selectinload(models.Recipe.ingredients).selectinload(
                models.RecipeIngredient.ingredient
            ),
            selectinload(models.Recipe.favorite_sides),
        )
    ).first()


def _requested_servings(request: Request) -> int | None:
    """``?servings=`` as an int, or ``None``.

    Parsed by hand rather than declared as a typed query parameter: the value
    arrives from a URL an unauthenticated visitor may have mangled, and a 422
    on a share page is a worse answer than ignoring the parameter.
    """
    raw = request.query_params.get("servings")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _absolute_og_image(request: Request, image_url: str | None) -> str | None:
    """RA-7: absolutise ``image_url`` for ``og:image``, safely.

    ``urljoin`` rather than concatenation, because ``image_url`` is user data:
    concatenating a base with ``https://evil.example/x.jpg`` yields a URL whose
    authority is the attacker's, and concatenating one with ``javascript:`` is
    worse. ``urljoin`` resolves an absolute value to itself (so a legitimate CDN
    image still works) and ``safe_url`` then drops any scheme we will not emit.
    """
    if not image_url:
        return None
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    base = f"{base}/" if base else str(request.base_url)
    return public_markup.safe_url(urljoin(base, image_url))


@router.get("/s/{token}", include_in_schema=False)
def share_page(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(optional_current_user),
):
    """Render a shared recipe, or refuse in a way that discloses nothing.

    ``include_in_schema=False`` (FC-9): ``/openapi.json`` and the ``/docs`` page
    it feeds are unauthenticated, so listing this route there would publish the
    shape of the sharing system -- and the fact that a bearer token lives in a
    URL path -- to any reader. It buys a caller nothing, since the token is the
    only thing that grants access and no schema can supply one.
    """
    share = shares.resolve(db, token)
    if share is None:
        return _not_found()

    if share.mode == "person":
        if current_user is None:
            # SH-23. Not a 401: the visitor may simply not be signed in yet, and
            # the page is the destination they were sent to.
            target = f"{_frontend_url()}/login?next=/s/{quote(token, safe='')}"
            return _with_headers(RedirectResponse(target, status_code=302))
        if not _is_named_recipient(share, current_user):
            # SH-24. Named-but-masked: enough to switch account, not enough to
            # learn an address from a URL you were forwarded.
            hint = _recipient_hint(db, share)
            return _with_headers(
                JSONResponse(
                    {
                        "detail": (
                            "This link was shared with a different account "
                            f"({hint})."
                        )
                    },
                    status_code=403,
                )
            )

    row = _load_recipe(db, share.recipe_id)
    if row is None:
        return _not_found()
    recipe, author = row

    public_recipe = PublicRecipe.from_recipe(recipe, author)
    requested = _requested_servings(request)
    if requested is not None:
        public_recipe = public_recipe.scaled_to(requested)

    lang = public_copy.pick_language(request.headers.get("accept-language"))

    response = public_blocks.public_templates().TemplateResponse(
        request,
        "public/recipe.html",
        {
            "request": request,
            "recipe": public_recipe,
            "blocks": public_blocks.build_blocks(
                public_recipe, recipe.page_layout
            ),
            "lang": lang,
            "t": lambda key, **fmt: public_copy.t(lang, key, **fmt),
            "copy_url": f"{_frontend_url()}/shared/{quote(token, safe='')}",
            "og_image": _absolute_og_image(request, recipe.image_url),
        },
    )

    # SH-26: the only thing a view records. No visitor identity, no IP, no per
    # visit row -- and stamped here rather than inside ``resolve`` so that a
    # valid token is not measurably slower than an invalid one (SH-27). It runs
    # after rendering so the commit cannot expire the loaded rows and force the
    # template to reload them (NF-2).
    share.last_viewed_at = datetime.utcnow()
    db.commit()

    return _with_headers(response)
