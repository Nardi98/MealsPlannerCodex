"""FastAPI application for Meals Planner Codex."""
from __future__ import annotations

import io
import json
import logging
import os
import random
import sys
import time
from datetime import date, datetime, timezone
from typing import Annotated, Any, Dict, List, NamedTuple, Optional
from urllib.parse import unquote_plus

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from starlette.datastructures import MutableHeaders
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

import crud
import mailer
import models
import ops_routes
import public_pages
import ratelimit
import schemas
import share_routes
import storage
import username_routes
import usernames
from mealplanner import planner
from mealplanner.seed import seed_system_ingredients, seed_system_tags
from database import SessionLocal, get_db
from scoping import scope
import auth_users

# The schema is owned by Alembic; the app never creates it. See
# ``migrations/README.md``.


def _bootstrap(session: Session) -> None:
    """Idempotent startup data: system tags per account, reserved handles.

    A function rather than a bare module-level block so the behaviour is
    reachable from a test; ``main`` still runs it once at import.
    """
    # Backfill the curated system tags for accounts that predate per-user
    # tagging. New accounts get their own set at registration (see
    # ``_create_account``), so this only has work to do for pre-existing users
    # and is a no-op once they are all caught up.
    seeded = set(
        session.execute(
            select(models.Tag.user_id).where(models.Tag.is_system.is_(True)).distinct()
        ).scalars()
    )
    for user_id in session.execute(select(models.User.id)).scalars():
        if user_id not in seeded:
            seed_system_tags(session, user_id)
    # UN-4: the reserved list must be in place before the first registration,
    # or the first person to sign up could claim ``admin``.
    usernames.seed_reserved(session)
    session.commit()


with SessionLocal() as _session:
    _bootstrap(_session)

app = FastAPI()

# Rate limiting for the authentication endpoints, keyed by client IP. The limit
# string is configurable (``AUTH_RATE_LIMIT``) and the whole limiter can be
# switched off (``RATE_LIMIT_ENABLED=0``) so the test suite is not throttled by
# shared in-process counters. Brute-force / enumeration attempts against the
# ``/auth/*`` write endpoints hit this first.
AUTH_RATE_LIMIT = os.environ.get("AUTH_RATE_LIMIT", "10/minute")
limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.environ.get("RATE_LIMIT_ENABLED", "1") != "0",
)
app.state.limiter = limiter

# The second, per-user limiter for the sharing endpoints (D-8). Registered on
# the same app so slowapi's middleware finds it, but kept as its own instance so
# the ``/auth/*`` behaviour above is unchanged. Phase 1/2 routers decorate with
# ``ratelimit.limiter.limit(...)``.
app.state.share_limiter = ratelimit.limiter

app.include_router(username_routes.router)
app.include_router(share_routes.router)
app.include_router(public_pages.router)
app.include_router(ops_routes.router)

# D-4 / RA-5: the public share page's stylesheet, served without JavaScript and
# without authentication. ``static`` is on the UN-4 reserved list so no username
# can ever shadow this path.
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
    name="static",
)


@app.exception_handler(RateLimitExceeded)
def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    return Response("Too Many Requests", status_code=429)


@app.exception_handler(RequestValidationError)
def _validation_handler(request: Request, exc: RequestValidationError) -> Response:
    """Return VIS-5's rejection as a 400 rather than Pydantic's generic 422.

    The requirement names the status and the message, and a client asking for a
    capability that does not exist yet deserves that answer rather than a field
    error. Every other validation failure keeps FastAPI's normal 422 shape.
    """
    for error in exc.errors():
        if schemas.PUBLIC_VISIBILITY_MESSAGE in str(error.get("msg", "")):
            return JSONResponse(
                status_code=400,
                content={"detail": schemas.PUBLIC_VISIBILITY_MESSAGE},
            )
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})


# Configuration for the auth flows read at request time.
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
# Q-1: the origin share URLs are built against. Share links are forwarded and
# persist in chat history, so the origin must be stable and configured rather
# than inferred. Empty means "fall back to the request base URL", which is
# correct in dev and wrong in production -- set it there.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/auth"

_VALID_SAMESITE = ("lax", "strict", "none")


class CookiePolicy(NamedTuple):
    samesite: str
    secure: bool


def cookie_policy() -> CookiePolicy:
    """The refresh cookie's cross-site attributes (``COOKIE_SAMESITE``/``COOKIE_SECURE``).

    Read at call time rather than at import, like :func:`allowed_hosts`, so the
    values are configuration rather than something baked into the module.

    The default -- ``Lax`` and insecure -- is right for local development, where
    the SPA and the API share an origin over http. It is *wrong* for the
    deployment, where they are two Railway services on two different registrable
    domains: a ``Lax`` cookie is not sent on the cross-site ``/auth/refresh``
    XHR, so every session would end at the next page reload.

    Both failure modes below are ones browsers punish *silently* -- an unknown
    ``SameSite`` and ``None`` without ``Secure`` are each grounds for dropping
    the cookie without telling anyone -- which is precisely why they raise here.
    """
    samesite = os.environ.get("COOKIE_SAMESITE", "lax").strip().lower()
    secure = os.environ.get("COOKIE_SECURE", "0") == "1"
    if samesite not in _VALID_SAMESITE:
        raise RuntimeError(
            f"COOKIE_SAMESITE must be one of {_VALID_SAMESITE}, got {samesite!r}"
        )
    if samesite == "none" and not secure:
        raise RuntimeError(
            "COOKIE_SAMESITE=none requires COOKIE_SECURE=1; browsers reject a "
            "cross-site cookie that is not marked Secure."
        )
    return CookiePolicy(samesite=samesite, secure=secure)


# Fail at startup rather than at the first login if the pair is misconfigured.
cookie_policy()


def _set_refresh_cookie(response: Response, token: str) -> None:
    policy = cookie_policy()
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        token,
        max_age=auth_users.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite=policy.samesite,
        secure=policy.secure,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    # The clear must mirror the attributes it was set with: a ``delete_cookie``
    # whose SameSite/Secure differ is ignored by some browsers, which would
    # leave a logged-out user still holding a live refresh cookie.
    policy = cookie_policy()
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        samesite=policy.samesite,
        secure=policy.secure,
        httponly=True,
    )


def _issue_session(db: Session, response: Response, user: models.User) -> schemas.Token:
    """Mint an access token and a rotating refresh cookie for ``user``."""
    refresh, jti, expires_at = auth_users.create_refresh_token(str(user.id))
    crud.create_refresh_token(db, user_id=user.id, jti=jti, expires_at=expires_at)
    _set_refresh_cookie(response, refresh)
    return schemas.Token(access_token=auth_users.create_access_token(str(user.id)))


def _send_verification_email(email: str, user_id: int) -> None:
    _send_token_email(
        email, user_id, "verify", auth_users.VERIFY_TOKEN_EXPIRE_MINUTES,
        path="/verify-email", subject="Verify your email",
        blurb="Confirm your Meal Planner account",
    )


def _send_reset_email(email: str, user_id: int) -> None:
    _send_token_email(
        email, user_id, "reset", auth_users.RESET_TOKEN_EXPIRE_MINUTES,
        path="/reset-password", subject="Reset your password",
        blurb="Reset your Meal Planner password",
    )


def _send_token_email(
    email: str, user_id: int, token_type: str, expires_minutes: int,
    *, path: str, subject: str, blurb: str,
) -> None:
    """Email a ``{FRONTEND_URL}{path}?token=...`` link for a signed auth token."""
    token = auth_users.create_email_token(str(user_id), token_type, expires_minutes)
    mailer.send_email(
        to=email, subject=subject, body=f"{blurb}: {FRONTEND_URL}{path}?token={token}"
    )


# The single authentication mechanism: every route that touches user-owned data
# declares this, and scopes its queries to ``current_user.id``.
CurrentUser = Annotated[models.User, Depends(auth_users.get_current_user)]
Db = Annotated[Session, Depends(get_db)]


def _csv_env(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable into a list of entries.

    Blank entries are dropped and each is stripped, so a trailing comma or a
    space after one in a ``.env`` file cannot become an empty origin or host --
    which in an allowlist would either match nothing or, worse, be treated as a
    wildcard by whatever consumes it.
    """
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# Restrict CORS to the configured frontend origin(s). ``ALLOWED_ORIGINS`` is a
# comma-separated list; default to the local dev server. Credentials are only
# enabled when concrete origins are set (a wildcard + credentials is rejected by
# browsers and is a security smell).
_allowed_origins = _csv_env("ALLOWED_ORIGINS", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials="*" not in _allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def allowed_hosts() -> list[str]:
    """The ``Host`` values this deployment answers to (``ALLOWED_HOSTS``).

    ``Host`` is a *request header*, so it is attacker-controlled, and several
    things here derive absolute URLs from it when ``PUBLIC_BASE_URL`` is unset
    -- ``shares.share_url`` most importantly, since a forged host there yields
    a share link on the attacker's origin that the sharer forwards in good
    faith, handing over a bearer token. ``shares`` validates the *shape* of the
    header, which stops injection but not forgery: ``evil.example`` is a
    perfectly well-formed hostname. Only configuration can answer "is this host
    mine", which is what this is.

    Comma-separated, whitespace-tolerant, and ``["*"]`` when unset so that
    local development and the test suite need no configuration -- there is no
    attacker on a developer's laptop to forge anything. **Set it in every
    deployment**, alongside ``PUBLIC_BASE_URL``.
    """
    return _csv_env("ALLOWED_HOSTS") or ["*"]


# Applied after CORS in source order, which means Starlette runs it *first* --
# a forged Host is rejected with 400 before any handler, and therefore before
# anything can build a URL from it.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts())


class NoIndexMiddleware:
    """FC-9 / FC-10: stamp ``X-Robots-Tag: noindex, nofollow`` on every response.

    ``public_pages`` already sets this on the share page, which is the surface
    carrying user content. This is the *default* underneath it, and it exists
    because the surfaces that lacked it were the ones nobody thought about:
    FastAPI's ``/docs``, ``/docs/oauth2-redirect`` and ``/redoc`` are full HTML
    pages, are served unauthenticated, and enumerate the entire API. An indexed
    ``/docs`` is a published map of the product to anyone who has never seen it.

    Applied to every response rather than only to HTML ones for two reasons:
    the header is meaningless-but-harmless on JSON, and a rule with no
    exceptions is a rule a future route cannot fall out of by being added with
    a content type nobody predicted. Routes that set their own value keep it --
    ``public_pages.PAGE_HEADERS`` is more specific and is left to win, which
    ``setdefault`` is what guarantees.

    Written as raw ASGI rather than ``@app.middleware("http")``. That decorator
    is ``BaseHTTPMiddleware``, which per request spins up an anyio task group
    and a pair of memory object streams and then re-pumps every response body
    chunk through them -- a large amount of machinery for one ``setdefault`` on
    a header dict, and it would put the ``/static`` mount's streamed
    ``FileResponse`` bodies through that pump too. Touching only the
    ``http.response.start`` message leaves bodies, streaming, and background
    tasks entirely alone.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_header(message):
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).setdefault(
                    "X-Robots-Tag", "noindex, nofollow"
                )
            await send(message)

        await self.app(scope, receive, send_with_header)


app.add_middleware(NoIndexMiddleware)


# One structured line per request. There is no error-tracking service wired up,
# so the platform's log view is the only account of what a tester hit when they
# report that something broke, and uvicorn's default access log -- a bare
# ``"GET /path HTTP/1.1" 200`` string -- is not something you can filter or
# aggregate. JSON is, and it costs one ``dumps`` per request.
ACCESS_LOGGER_NAME = "mealplanner.access"
_access_logger = logging.getLogger(ACCESS_LOGGER_NAME)
# Wired to stdout explicitly. Uvicorn configures its own loggers and leaves the
# root logger without a handler, so a logger that only propagates emits nothing
# at all in the deployed container -- which is precisely where these lines are
# the only record of what a request did. The message is already JSON, so the
# formatter passes it through untouched.
if not _access_logger.handlers:
    _access_handler = logging.StreamHandler(sys.stdout)
    _access_handler.setFormatter(logging.Formatter("%(message)s"))
    _access_logger.addHandler(_access_handler)
_access_logger.setLevel(logging.INFO)


def _query_keys(query_string: bytes) -> list[str]:
    """The *names* of the query parameters, decoded, sorted and de-duplicated.

    Splitting on the separators beats ``parse_qs`` here: ``parse_qs`` decodes
    and materialises every *value* into lists, and the values are the one part
    of a query string that must never reach a log -- ``/verify-email?token=...``
    and ``/reset-password?token=...`` both carry a live credential, and a log
    line outlives the token it would leak.
    """
    if not query_string:
        return []
    query = query_string.decode("latin-1")
    return sorted({unquote_plus(pair.split("=", 1)[0]) for pair in query.split("&") if pair})


class AccessLogMiddleware:
    """Log method, path, status and duration for every HTTP request.

    Query *keys* are recorded but never their values. The values are exactly
    where the secrets are -- ``/verify-email?token=...`` and
    ``/reset-password?token=...`` both put a live credential in the query string
    -- and a log line outlives the token it would leak. Knowing which parameters
    were present is enough to reproduce a bug report.

    Raw ASGI for the same reason as :class:`NoIndexMiddleware`: reading the
    status off ``http.response.start`` leaves bodies, streaming and background
    tasks untouched, where ``BaseHTTPMiddleware`` would re-pump every chunk.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        started = time.perf_counter()
        status = 500

        async def send_with_log(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_log)
        finally:
            # In ``finally`` so a handler that raises past us is still recorded;
            # the 500 default above is what that case reports. Guarded on the
            # level so a quietened logger costs nothing on a path the platform
            # health probe alone hits continuously.
            if _access_logger.isEnabledFor(logging.INFO):
                _access_logger.info(json.dumps({
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "query_keys": _query_keys(scope.get("query_string", b"")),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }))


app.add_middleware(AccessLogMiddleware)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect the index route to the interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Return an empty response for browsers requesting a favicon."""
    return Response(status_code=204)


@app.post("/auth/register", response_model=schemas.UserOut, status_code=201)
@limiter.limit(AUTH_RATE_LIMIT)
def register(
    request: Request, payload: schemas.UserCreate, db: Db
) -> schemas.UserOut:
    """Register a new, unverified local account and email a verification link.

    The response is deliberately non-committal about whether the address was
    already taken: a duplicate registration neither errors nor reveals the
    existing account, so the endpoint cannot be used to enumerate users. The
    password is hashed on every path so both branches cost the same time.
    """
    hashed = auth_users.hash_password(payload.password)
    if payload.username is not None and not usernames.is_available(
        db, payload.username
    ):
        # UN-4/UN-5: a reserved or taken handle is rejected clearly. Unlike the
        # email, the handle is a *public* identifier, so saying it is taken
        # discloses nothing the availability endpoint (UN-7) does not.
        raise HTTPException(status_code=409, detail=usernames.CONFLICT_MESSAGE)
    existing = crud.get_user_by_email(db, payload.email)
    if existing is None:
        try:
            user = _create_account(
                db,
                email=payload.email,
                hashed_password=hashed,
                display_name=payload.display_name,
                username=payload.username,
            )
        except crud.UsernameTaken:
            # UN-2. The availability check above is a *hint*: it and the insert
            # are two statements, so two concurrent registrations of the same
            # handle both pass it and ``uq_user_username_lower`` decides. The
            # loser gets the identical 409 an ordinary conflict produces --
            # never a 500, and never a hint that it was a race, because the
            # answer to both is the same: pick another handle.
            raise HTTPException(status_code=409, detail=usernames.CONFLICT_MESSAGE)
        # UN-5: a local sign-up chooses its own handle, so it counts as
        # confirmed from the start (D-7) and skips the selection step. Stamped
        # by ``crud.create_user`` itself, which is the only place that knows
        # whether the handle was chosen or derived.
        _send_verification_email(user.email, user.id)
        user_id = user.id
        handle = user.username
        confirmed = user.username_confirmed
    else:
        # Neutral path: never confirm the address exists, never resend. The
        # handle echoed back is the submitted one, not the existing account's:
        # returning the real handle would turn this endpoint into the email
        # enumeration oracle the neutral response exists to prevent.
        user_id = existing.id
        handle = usernames.normalise(payload.username) or ""
        confirmed = payload.username is not None

    return schemas.UserOut(
        id=user_id,
        email=models.normalize_email(payload.email),
        username=handle,
        username_confirmed=confirmed,
        display_name=payload.display_name,
        auth_provider="local",
        default_people=models.DEFAULT_PEOPLE,
        email_verified=False,
    )


def _create_account(
    db: Session,
    *,
    email: str,
    hashed_password: str | None = None,
    display_name: str | None = None,
    auth_provider: str = "local",
    google_sub: str | None = None,
    email_verified: bool = False,
    username: str | None = None,
) -> models.User:
    """Create a user and give it the starter data a fresh account needs.

    New accounts start with their own copy of the curated system tags and the
    starter ingredient library, so tagging and recipe entry work out of the box
    without leaking another user's data.

    ``username=None`` leaves ``crud.create_user`` to derive a provisional handle
    and leaves ``username_changed_at`` NULL, which is how a Google sign-up ends
    up in the "unconfirmed handle" state that forces selection (D-7, UN-6).
    """
    user = crud.create_user(
        db,
        email=email,
        hashed_password=hashed_password,
        display_name=display_name,
        auth_provider=auth_provider,
        google_sub=google_sub,
        email_verified=email_verified,
        username=username,
    )
    seed_system_tags(db, user.id)
    seed_system_ingredients(db, user.id)
    return user


@app.post("/auth/login", response_model=schemas.Token)
@limiter.limit(AUTH_RATE_LIMIT)
def login(
    request: Request, response: Response, payload: schemas.LoginRequest, db: Db
) -> schemas.Token:
    user = crud.get_user_by_email(db, payload.email)
    if user is None or user.hashed_password is None:
        # Run a dummy verify so a missing account is indistinguishable, by
        # timing, from a wrong password (no account-enumeration oracle).
        auth_users.verify_password(payload.password, auth_users.DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not auth_users.verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Email address not verified")
    return _issue_session(db, response, user)


@app.post("/auth/google", response_model=schemas.Token)
@limiter.limit(AUTH_RATE_LIMIT)
def login_with_google(
    request: Request, response: Response, payload: schemas.GoogleLoginRequest, db: Db
) -> schemas.Token:
    """Exchange a Google ID token for one of our JWTs, creating the account if new."""
    try:
        claims = auth_users.verify_google_token(payload.credential)
    except ValueError as exc:
        raise HTTPException(
            status_code=401, detail=f"Invalid Google credential: {exc}"
        )

    google_sub = claims["sub"]
    email = claims["email"]
    user = crud.get_user_by_google_sub(db, google_sub) or crud.get_user_by_email(
        db, email
    )
    if user is None:
        # Creating an account from a Google identity is only safe once Google has
        # verified the address, exactly as for the link path below; otherwise a
        # Google sign-up with someone else's unverified email would seed an
        # account under an address the caller does not control.
        if not claims.get("email_verified"):
            raise HTTPException(
                status_code=401, detail="Google email is not verified"
            )
        user = _create_account(
            db,
            email=email,
            display_name=claims.get("name"),
            auth_provider="google",
            google_sub=google_sub,
            email_verified=True,
        )
    elif user.google_sub is None:
        # Claiming an existing account by email is only safe once Google has
        # verified the address; otherwise anyone could sign up at Google with
        # someone else's email and inherit their account.
        if not claims.get("email_verified"):
            raise HTTPException(
                status_code=401, detail="Google email is not verified"
            )
        user.google_sub = google_sub
        db.commit()
    return _issue_session(db, response, user)


@app.post("/auth/refresh", response_model=schemas.Token)
@limiter.limit(AUTH_RATE_LIMIT)
def refresh_session(request: Request, response: Response, db: Db) -> schemas.Token:
    """Rotate the refresh cookie and return a fresh access token.

    The presented refresh token is revoked and replaced (rotation), so a stolen
    cookie is single-use. Missing, malformed, revoked, or expired tokens all
    yield ``401``.
    """
    unauthorized = HTTPException(status_code=401, detail="Invalid refresh token")
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise unauthorized
    payload = auth_users.decode_refresh_token(token)
    if payload is None:
        raise unauthorized
    stored = crud.get_refresh_token(db, payload["jti"])
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if stored is None or stored.revoked or stored.expires_at < now:
        raise unauthorized

    crud.revoke_refresh_token(db, stored)
    user = crud.get_user(db, stored.user_id)
    if user is None:
        raise unauthorized
    return _issue_session(db, response, user)


@app.post("/auth/logout", status_code=204)
def logout(request: Request, db: Db) -> Response:
    """Revoke the presented refresh token and clear the cookie."""
    response = Response(status_code=204)
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token:
        payload = auth_users.decode_refresh_token(token)
        if payload is not None:
            stored = crud.get_refresh_token(db, payload["jti"])
            if stored is not None and not stored.revoked:
                crud.revoke_refresh_token(db, stored)
    _clear_refresh_cookie(response)
    return response


@app.post("/auth/verify-email")
@limiter.limit(AUTH_RATE_LIMIT)
def verify_email(
    request: Request, payload: schemas.VerifyEmailRequest, db: Db
) -> dict:
    """Mark the account named by a valid verification token as verified."""
    subject = auth_users.decode_email_token(payload.token, "verify")
    user = crud.get_user(db, int(subject)) if subject is not None else None
    if user is None:
        raise HTTPException(
            status_code=400, detail="Invalid or expired verification token"
        )
    crud.set_email_verified(db, user, True)
    return {"detail": "Email verified"}


@app.post("/auth/forgot-password")
@limiter.limit(AUTH_RATE_LIMIT)
def forgot_password(
    request: Request, payload: schemas.ForgotPasswordRequest, db: Db
) -> dict:
    """Email a reset link if the address maps to a local account.

    Always returns the same neutral ``200`` so the endpoint cannot be used to
    discover which addresses have accounts.
    """
    user = crud.get_user_by_email(db, payload.email)
    if user is not None and user.hashed_password is not None:
        _send_reset_email(user.email, user.id)
    return {"detail": "If that account exists, a reset email has been sent"}


@app.post("/auth/reset-password")
@limiter.limit(AUTH_RATE_LIMIT)
def reset_password(
    request: Request, payload: schemas.ResetPasswordRequest, db: Db
) -> dict:
    """Set a new password from a valid reset token and revoke all sessions."""
    subject = auth_users.decode_email_token(payload.token, "reset")
    user = crud.get_user(db, int(subject)) if subject is not None else None
    if user is None:
        raise HTTPException(
            status_code=400, detail="Invalid or expired reset token"
        )
    user.hashed_password = auth_users.hash_password(payload.new_password)
    db.commit()
    # A password change must not leave old refresh sessions alive.
    crud.revoke_all_refresh_tokens(db, user.id)
    return {"detail": "Password updated"}


@app.get("/auth/me", response_model=schemas.UserOut)
def read_me(
    current_user: CurrentUser,
) -> models.User:
    return current_user


@app.put("/auth/me/default-people", response_model=schemas.UserOut)
def set_default_people(
    payload: schemas.DefaultPeopleIn,
    db: Db,
    current_user: CurrentUser,
) -> models.User:
    """Set the user's default people count and apply it to the given range.

    Overwrites ``Meal.people`` for every meal in ``[start_date, end_date]`` and
    stores ``people`` as the default for future meals.
    """
    crud.set_default_people(
        db,
        payload.people,
        payload.start_date,
        payload.end_date,
        current_user.id,
    )
    db.refresh(current_user)
    return current_user


@app.get("/recipes", response_model=List[schemas.RecipeOut])
def read_recipes(
    db: Db,
    current_user: CurrentUser,
) -> List[schemas.RecipeOut]:
    stmt = scope(
        select(models.Recipe).options(
            selectinload(models.Recipe.tags),
            # RecipeOut exposes favorite_side_ids, so without this the
            # serialiser lazy-loads the pairing once per recipe.
            selectinload(models.Recipe.favorite_sides),
            selectinload(models.Recipe.ingredients).selectinload(
                models.RecipeIngredient.ingredient
            ),
        ),
        models.Recipe.user_id,
        current_user.id,
    )
    return db.execute(stmt).scalars().all()


@app.get("/recipes/{recipe_id}", response_model=schemas.RecipeOut)
def read_recipe(
    recipe_id: int,
    db: Db,
    current_user: CurrentUser,
) -> schemas.RecipeOut:
    recipe = crud.get_recipe(db, recipe_id, current_user.id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _resolve_favorite_sides(
    payload: schemas.RecipeIn, db: Session, user_id: int
) -> List[models.Recipe]:
    """Load the caller's own side recipes named by ``payload.favorite_side_ids``.

    Rejects anything the caller doesn't own or that isn't a side dish, so a
    stale or hand-crafted id can't quietly pair a main with a main. The same
    rule is applied leniently on the import path (``crud.import_data``), which
    drops bad pairings rather than failing a whole file.
    """
    side_ids = list(dict.fromkeys(payload.favorite_side_ids))  # dedupe, keep order
    if not side_ids:
        return []
    if not models.takes_favorite_sides(payload.course):
        raise HTTPException(
            status_code=400,
            detail=f"A {payload.course!r} recipe is not served with a side dish",
        )
    stmt = scope(
        select(models.Recipe).where(models.Recipe.id.in_(side_ids)),
        models.Recipe.user_id,
        user_id,
    )
    found = {r.id: r for r in db.execute(stmt).scalars()}
    resolved: List[models.Recipe] = []
    for side_id in side_ids:
        side = found.get(side_id)
        if side is None:
            raise HTTPException(
                status_code=400, detail=f"Unknown favorite side: {side_id}"
            )
        if not models.is_side_dish(side):
            raise HTTPException(
                status_code=400,
                detail=f"Recipe {side.title!r} is not a side dish",
            )
        resolved.append(side)
    return resolved


def _payload_to_data(payload: schemas.RecipeIn, db: Session, user_id: int) -> dict:
    tags = [crud.get_or_create_tag(db, name, user_id) for name in payload.tags]
    ingredients: List[models.RecipeIngredient] = []
    for ing in payload.ingredients:
        if ing.id is None and not ing.name:
            continue
        ingredient_obj = crud.get_or_create_ingredient(
            db, ing.id, ing.name, ing.unit, user_id
        )
        # Seasonality belongs to the shared ingredient row, and the row is owned
        # by the ``/ingredients`` endpoints -- a recipe payload only *names* it.
        # So seed it when this call just created the row, and never touch a row
        # that already existed: the SPA's recipe forms do not collect the field
        # and ``serialiseRecipe`` fills the gap with an all-year default, which
        # assigning unconditionally would stamp onto every ingredient of every
        # recipe anyone saves -- flattening the seasonality the account was
        # seeded with, for every other recipe using that ingredient too, and
        # with it the planner's seasonality score.
        #
        # ``id is None`` is precisely "added to the session by the call above
        # and not yet flushed"; anything resolved by id or by name is already
        # persistent.
        if ingredient_obj.id is None:
            ingredient_obj.season_months = ing.season_months or list(range(1, 13))
        ingredients.append(
            models.RecipeIngredient(
                ingredient=ingredient_obj,
                quantity=ing.quantity,
                unit=ing.unit,
            )
        )
    return {
        "title": payload.title,
        "course": payload.course,
        "procedure": payload.procedure,
        "bulk_prep": payload.bulk_prep,
        "image_url": payload.image_url,
        # ``RecipeIn`` has already rejected ``public`` (VIS-5), so anything
        # reaching here is ``private`` or ``unlisted``. Note the attribution
        # snapshot is deliberately absent: it is not a client-writable field
        # (AT-4).
        "visibility": payload.visibility,
        "tags": tags,
        "ingredients": ingredients,
        "favorite_sides": _resolve_favorite_sides(payload, db, user_id),
    }


@app.post(
    "/recipes",
    response_model=schemas.RecipeOut,
    status_code=201,
)
def create_recipe(
    payload: schemas.RecipeIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.RecipeOut:
    data = _payload_to_data(payload, db, current_user.id)
    return crud.create_recipe(db, user_id=current_user.id, **data)


_MAX_IMAGE_BYTES = 5 * 1024 * 1024


@app.post("/recipes/upload-image", status_code=201)
async def upload_recipe_image(
    request: Request,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> dict:
    """Store an uploaded image and return an absolute URL that serves it back."""
    data = await file.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 5 MB limit")
    try:
        key = storage.save_image(data, file.content_type or "")
    except ValueError:
        raise HTTPException(status_code=415, detail="Unsupported image type")
    image_url = f"{str(request.base_url).rstrip('/')}/recipes/images/{key}"
    return {"image_url": image_url}


@app.get("/recipes/images/{key:path}")
def serve_recipe_image(key: str) -> Response:
    """Stream a previously uploaded image by its storage key."""
    try:
        data, content_type = storage.open_image(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=data, media_type=content_type)


@app.put(
    "/recipes/{recipe_id}",
    response_model=schemas.RecipeOut,
)
def update_recipe(
    recipe_id: int,
    payload: schemas.RecipeIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.RecipeOut:
    data = _payload_to_data(payload, db, current_user.id)
    recipe = crud.update_recipe(db, recipe_id, current_user.id, **data)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@app.delete(
    "/recipes/{recipe_id}",
    status_code=204,
)
def delete_recipe(
    recipe_id: int,
    db: Db,
    current_user: CurrentUser,
) -> Response:
    deleted = crud.delete_recipe(db, recipe_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return Response(status_code=204)


@app.get("/tags", response_model=List[schemas.TagOut])
def read_tags(
    db: Db,
    current_user: CurrentUser,
) -> List[schemas.TagOut]:
    stmt = scope(select(models.Tag), models.Tag.user_id, current_user.id)
    return db.execute(stmt).scalars().all()


def _ingredient_recipe_count(db: Session, ingredient_id: int) -> int:
    return db.scalar(
        select(func.count(models.RecipeIngredient.recipe_id)).where(
            models.RecipeIngredient.ingredient_id == ingredient_id
        )
    ) or 0


@app.get("/ingredients", response_model=List[schemas.IngredientSummary])
def search_ingredients(
    db: Db,
    current_user: CurrentUser,
    search: str = "",
) -> List[schemas.IngredientSummary]:
    stmt = scope(
        select(
            models.Ingredient,
            func.count(models.RecipeIngredient.recipe_id).label("recipe_count"),
        )
        .outerjoin(models.Ingredient.recipes)
        .group_by(models.Ingredient.id)
        .order_by(models.Ingredient.name),
        models.Ingredient.user_id,
        current_user.id,
    )
    if search:
        stmt = stmt.where(models.Ingredient.name.ilike(f"{search}%")).limit(10)
    rows = db.execute(stmt).all()
    return [
        schemas.IngredientSummary(
            id=ing.id,
            name=ing.name,
            season_months=ing.season_months or [],
            unit=ing.unit,
            categories=ing.categories or [],
            recipe_count=count,
        )
        for ing, count in rows
    ]


@app.get(
    "/ingredients/similar",
    response_model=List[schemas.IngredientSummary],
)
def similar_ingredients(
    name: str,
    db: Db,
    current_user: CurrentUser,
    exclude_id: int | None = None,
    threshold: float = 0.8,
) -> List[schemas.IngredientSummary]:
    matches = crud.find_similar_ingredients(
        db, name, exclude_id=exclude_id, threshold=threshold, user_id=current_user.id
    )
    return [
        schemas.IngredientSummary(
            id=ing.id,
            name=ing.name,
            season_months=ing.season_months or [],
            unit=ing.unit,
            categories=ing.categories or [],
            recipe_count=_ingredient_recipe_count(db, ing.id),
        )
        for ing in matches
    ]


@app.get(
    "/ingredients/duplicates",
    response_model=List[schemas.DuplicatePair],
)
def duplicate_ingredients(
    db: Db,
    current_user: CurrentUser,
    threshold: float = 0.8,
) -> List[schemas.DuplicatePair]:
    pairs = crud.find_duplicate_pairs(
        db, threshold=threshold, user_id=current_user.id
    )

    def summary(ing: models.Ingredient) -> schemas.IngredientSummary:
        return schemas.IngredientSummary(
            id=ing.id,
            name=ing.name,
            season_months=ing.season_months or [],
            unit=ing.unit,
            categories=ing.categories or [],
            recipe_count=_ingredient_recipe_count(db, ing.id),
        )

    return [
        schemas.DuplicatePair(a=summary(a), b=summary(b), score=score)
        for a, b, score in pairs
    ]


@app.post(
    "/ingredients/merge",
    response_model=schemas.IngredientSummary,
)
def merge_ingredients_endpoint(
    payload: schemas.IngredientMergeRequest,
    db: Db,
    current_user: CurrentUser,
) -> schemas.IngredientSummary:
    try:
        merged = crud.merge_ingredients(
            db,
            payload.source_id,
            payload.target_id,
            surviving_unit=payload.surviving_unit,
            conversion_factor=payload.conversion_factor,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if merged is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return schemas.IngredientSummary(
        id=merged.id,
        name=merged.name,
        season_months=merged.season_months or [],
        unit=merged.unit,
        categories=merged.categories or [],
        recipe_count=_ingredient_recipe_count(db, merged.id),
    )


@app.post(
    "/ingredients",
    response_model=schemas.IngredientSummary,
    status_code=201,
)
def create_ingredient(
    payload: schemas.IngredientCreate,
    db: Db,
    current_user: CurrentUser,
) -> schemas.IngredientSummary:
    ingredient = crud.create_ingredient(
        db,
        payload.name,
        payload.unit,
        payload.season_months,
        payload.categories,
        user_id=current_user.id,
    )
    return schemas.IngredientSummary(
        id=ingredient.id,
        name=ingredient.name,
        season_months=ingredient.season_months or [],
        unit=ingredient.unit,
        categories=ingredient.categories or [],
        recipe_count=0,
    )


@app.put(
    "/ingredients/{ingredient_id}",
    response_model=schemas.IngredientSummary,
)
def update_ingredient(
    ingredient_id: int,
    payload: schemas.IngredientUpdate,
    db: Db,
    current_user: CurrentUser,
) -> schemas.IngredientSummary:
    ingredient = crud.get_ingredient(db, ingredient_id, current_user.id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    ingredient.name = payload.name
    ingredient.season_months = payload.season_months
    ingredient.unit = payload.unit
    ingredient.categories = payload.categories
    db.commit()
    return schemas.IngredientSummary(
        id=ingredient.id,
        name=ingredient.name,
        season_months=ingredient.season_months or [],
        unit=ingredient.unit,
        categories=ingredient.categories or [],
        recipe_count=_ingredient_recipe_count(db, ingredient.id),
    )


@app.get(
    "/ingredients/{ingredient_id}/recipes",
    response_model=List[schemas.RecipeSummary],
)
def ingredient_recipes(
    ingredient_id: int,
    db: Db,
    current_user: CurrentUser,
) -> List[schemas.RecipeSummary]:
    ingredient = crud.get_ingredient(db, ingredient_id, current_user.id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    recipes = crud.get_recipes_by_ingredient(db, ingredient_id, current_user.id)
    return [schemas.RecipeSummary(id=r.id, title=r.title) for r in recipes]


@app.delete(
    "/ingredients/{ingredient_id}",
    status_code=204,
)
def delete_ingredient(
    ingredient_id: int,
    db: Db,
    current_user: CurrentUser,
    force: bool = False,
) -> Response:
    deleted = crud.delete_ingredient(
        db, ingredient_id, force=force, user_id=current_user.id
    )
    if deleted is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if deleted is False:
        raise HTTPException(
            status_code=400, detail="Ingredient is referenced by recipes"
        )
    return Response(status_code=204)


# A day is served as an array indexed by `meal_number` (Lunch=1, Dinner=2), so
# an empty slot is a `None` hole rather than a missing element -- a day holding
# only a dinner serves as `[null, {...}]`. The slot list must therefore admit
# `None`, or such a day fails response validation with a 500.
PlanOut = Dict[str, List[Optional[schemas.MealOut]]]


# DEPRECATED: the legacy `/plan` routes below are kept for backward
# compatibility only. Prefer the `/meal-plans` paths. Removal is scheduled no
# earlier than 2026-10-01; do not add new behaviour to the `/plan` paths.
@app.get("/plan", response_model=PlanOut)
@app.get("/meal-plans", response_model=PlanOut)
def get_plan(
    db: Db,
    current_user: CurrentUser,
    plan_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> PlanOut:
    return crud.get_plan(db, plan_date, start_date, end_date, current_user.id)


@app.post(
    "/plan",
    response_model=PlanOut,
)
@app.post(
    "/meal-plans",
    response_model=PlanOut,
)
def set_plan(
    payload: schemas.MealPlanCreate,
    db: Db,
    current_user: CurrentUser,
    force: bool = False,
) -> PlanOut:
    plan_dates = [
        day if isinstance(day, date) else date.fromisoformat(day)
        for day in payload.plan.keys()
    ]
    stmt = scope(
        select(models.MealPlan.plan_date).where(
            models.MealPlan.plan_date.in_(plan_dates)
        ),
        models.MealPlan.user_id,
        current_user.id,
    )
    existing = db.execute(stmt).scalars().all()
    if existing and not force:
        conflicts = [d.isoformat() for d in existing]
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=409, content={"conflicts": conflicts})

    crud.set_meal_plan(db, payload.plan, current_user.id)
    return crud.get_plan(db, payload.plan_date, user_id=current_user.id)


@app.delete(
    "/plan",
    response_model=Dict[str, int],
)
@app.delete(
    "/meal-plans",
    response_model=Dict[str, int],
)
def delete_meal_plans(
    db: Db,
    current_user: CurrentUser,
    start_date: date = Query(..., description="Inclusive start date for deletion"),
    end_date: date = Query(..., description="Inclusive end date for deletion"),
) -> Dict[str, int]:
    if end_date < start_date:
        raise HTTPException(
            status_code=422, detail="end_date must not be before start_date"
        )

    deleted = crud.delete_meal_plans(db, start_date, end_date, current_user.id)
    return {"deleted": deleted}


@app.get("/plan/settings", response_model=Dict[str, Any])
def plan_settings(
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, Any]:
    """Return the caller's plan settings (defaults + their stored overrides)."""

    return crud.get_plan_settings(db, current_user.id)


@app.put("/plan/settings", response_model=Dict[str, Any])
def update_plan_settings(
    payload: Dict[str, Any],
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, Any]:
    """Persist the caller's plan-setting overrides and return the merged view."""

    return crud.set_plan_settings(db, current_user.id, payload)


@app.post(
    "/meal-plans/accept",
    response_model=schemas.MealOut,
)
def toggle_meal_acceptance(
    payload: schemas.MealAcceptanceIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.MealOut:
    meal = crud.mark_meal_accepted(
        db, payload.plan_date, payload.meal_number, payload.accepted,
        current_user.id,
    )
    if meal is None or meal.recipe is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return schemas.MealOut(**crud.meal_item(meal))


@app.post(
    "/meal-plans/people",
    response_model=schemas.MealOut,
)
def set_meal_people(
    payload: schemas.MealPeopleIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.MealOut:
    meal = crud.set_meal_people(
        db, payload.plan_date, payload.meal_number, payload.people,
        current_user.id,
    )
    if meal is None or meal.recipe is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return schemas.MealOut(**crud.meal_item(meal))


@app.post("/meal-plans/swap")
def swap_meals(
    payload: schemas.MealSwapIn,
    db: Db,
    current_user: CurrentUser,
) -> dict:
    result = crud.swap_meals(
        db,
        (payload.a.plan_date, payload.a.meal_number),
        (payload.b.plan_date, payload.b.meal_number),
        current_user.id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return {"ok": True}


@app.post(
    "/meal-plans/side",
    response_model=schemas.MealOut,
)
def upsert_side_dish(
    payload: schemas.MealSideIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.MealOut:
    if payload.index is None:
        meal = crud.add_meal_side(
            db, payload.plan_date, payload.meal_number, payload.side_id,
            current_user.id,
        )
    else:
        meal = crud.replace_meal_side(
            db, payload.plan_date, payload.meal_number, payload.index,
            payload.side_id, current_user.id,
        )
    if meal is None or meal.recipe is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return schemas.MealOut(**crud.meal_item(meal))


@app.delete(
    "/meal-plans/side",
    response_model=schemas.MealOut,
)
def delete_side_dish(
    payload: schemas.MealSideRemoveIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.MealOut:
    meal = crud.remove_meal_side(
        db, payload.plan_date, payload.meal_number, payload.index, current_user.id
    )
    if meal is None or meal.recipe is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return schemas.MealOut(**crud.meal_item(meal))


@app.post("/feedback/accept")
def feedback_accept(
    payload: schemas.FeedbackIn,
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, str]:
    """Record user acceptance of a recipe."""

    if crud.accept_recipe(
        db, payload.title, payload.consumed_date, current_user.id
    ) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {"status": "ok"}


@app.post("/feedback/reject")
def feedback_reject(
    payload: schemas.FeedbackIn,
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, Optional[str]]:
    """Record user rejection of a recipe and suggest a replacement."""

    if crud.reject_recipe(db, payload.title, current_user.id) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    existing = set(crud.list_planned_titles(db, current_user.id))
    existing.add(payload.title)
    available = list(
        set(
            crud.list_recipe_titles(
                db, courses=["main", "first-course"], user_id=current_user.id
            )
        )
        - existing
    )
    replacement = random.choice(available) if available else None
    return {"replacement": replacement}


@app.post("/meal-plans/generate")
def generate_plan_endpoint(
    payload: schemas.MealPlanGenerate,
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, List[Dict[str, object]]]:
    days = (payload.end - payload.start).days + 1
    settings = crud.get_plan_settings(db, current_user.id)
    # The tag-penalty weight is a per-user profile setting, not a per-plan knob,
    # so it comes from the stored settings; the request field is only a fallback.
    tag_penalty_weight = settings.get(
        "tag_penalty_weight", payload.tag_penalty_weight
    )
    fridge_ingredients = {item.ingredient_id: item.count for item in payload.fridge}
    slots = planner.generate_plan(
        db,
        user_id=current_user.id,
        plan_settings=settings,
        start=payload.start,
        days=days,
        meals_per_day=payload.meals_per_day,
        keep_days=payload.keep_days,
        bulk_leftovers=payload.bulk_leftovers,
        epsilon=payload.epsilon,
        avoid_tags=payload.avoid_tags,
        reduce_tags=payload.reduce_tags,
        seasonality_weight=payload.seasonality_weight,
        recency_weight=payload.recency_weight,
        tag_penalty_weight=tag_penalty_weight,
        bulk_bonus_weight=payload.bulk_bonus_weight,
        fridge_ingredients=fridge_ingredients,
        return_slots=True,
    )
    result: Dict[str, List[Dict[str, object]]] = {}
    for slot in slots:
        recipe = slot.recipe
        if recipe is None:
            raise HTTPException(status_code=404, detail="Recipe not found")
        result.setdefault(slot.date.isoformat(), []).append(
            {
                "id": recipe.id,
                "title": recipe.title,
                "leftover": slot.leftover,
                "side_ids": slot.side_ids,
            }
        )
    return result


@app.post("/side-dishes/generate")
def generate_side_dish_endpoint(
    payload: schemas.SideDishGenerate,
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, object]:
    try:
        recipe = planner.generate_side_dish(
            db,
            user_id=current_user.id,
            avoid_tags=payload.avoid_tags,
            reduce_tags=payload.reduce_tags,
            avoid_titles=payload.avoid_titles,
            epsilon=payload.epsilon,
            keep_days=payload.keep_days,
            bulk_leftovers=payload.bulk_leftovers,
            seasonality_weight=payload.seasonality_weight,
            recency_weight=payload.recency_weight,
            tag_penalty_weight=payload.tag_penalty_weight,
            bulk_bonus_weight=payload.bulk_bonus_weight,
        )
    except ValueError as exc:  # pragma: no cover - error path
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": recipe.id, "title": recipe.title}


@app.get("/data/export")
def export_data_endpoint(
    db: Db,
    current_user: CurrentUser,
) -> Response:
    data = crud.export_data(db, current_user.id)
    return Response(content=data, media_type="application/json")


@app.post("/data/import")
def import_data_endpoint(
    payload: Dict[str, Any],
    db: Db,
    current_user: CurrentUser,
    mode: str = "overwrite",
) -> Dict[str, str]:
    try:
        crud.import_data(
            io.StringIO(json.dumps(payload)), db, mode=mode, user_id=current_user.id
        )
    except ValueError as exc:  # pragma: no cover - value error path
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}


@app.delete("/data")
def clear_data_endpoint(
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, str]:
    crud.clear_data(db, current_user.id)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
