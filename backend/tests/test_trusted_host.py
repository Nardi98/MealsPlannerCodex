"""``ALLOWED_HOSTS`` / ``TrustedHostMiddleware``: the control behind the Host fallback.

The problem this closes
-----------------------
``shares.share_url`` and ``public_pages._absolute_og_image`` fall back to the
request's ``Host`` header when ``PUBLIC_BASE_URL`` is unset. ``Host`` is
attacker-controlled: it is a request header, and nothing in the framework
checks it against the deployment's real name. So an attacker who can reach the
share-creation endpoint as themselves can send ``Host: evil.example`` and get
back ``https://evil.example/s/<token>`` -- a link that *looks* like the
product's, that the sharer then forwards to a friend, and that delivers the
share token to the attacker's server the moment it is clicked. The token is a
bearer capability, so that is a complete compromise of the shared recipe.

``shares`` already validates the derived host against a strict hostname pattern.
That blocks *injection* -- ``evil.example/@real``, embedded credentials, CR/LF --
but ``evil.example`` is a perfectly well-formed hostname, so it does nothing
about *forgery*. A regex cannot fix this, because the question is not "is this
string shaped like a host" but "is this host mine", and only configuration knows
the answer.

Why ``TrustedHostMiddleware`` and not "make ``PUBLIC_BASE_URL`` mandatory"
-------------------------------------------------------------------------
Both were on the table. Mandating ``PUBLIC_BASE_URL`` fixes the two call sites
that read the header today; ``TrustedHostMiddleware`` fixes the *header*, which
means it also covers the third call site somebody adds next year without
remembering this note, plus password-reset links, plus web-cache poisoning,
plus anything else that ever reaches for ``request.base_url``. It rejects the
forged request outright, before any handler runs, rather than sanitising one
output derived from it. That is the difference between a control and a patch,
so it is the one chosen here.

The default is permissive (``*``) so that local development and this test suite
-- where the header is not attacker-controlled, because there is no attacker --
keep working with no configuration. **Setting ``ALLOWED_HOSTS`` is therefore a
deployment prerequisite**, exactly like ``PUBLIC_BASE_URL``. It is not made
mandatory the way ``DATABASE_URL`` is because a wrong value here fails *closed*
in the most confusing possible way -- every request 400s with no clue why --
whereas a missing ``DATABASE_URL`` has an obviously correct error message.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

import main


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, ["*"]),
        ("", ["*"]),
        ("   ", ["*"]),
        ("mealplanner.app", ["mealplanner.app"]),
        ("mealplanner.app,www.mealplanner.app", ["mealplanner.app", "www.mealplanner.app"]),
        (" a.example , b.example ", ["a.example", "b.example"]),
        ("a.example,,b.example", ["a.example", "b.example"]),
        ("*.mealplanner.app", ["*.mealplanner.app"]),
    ],
)
def test_allowed_hosts_parsing(monkeypatch, raw, expected):
    """Comma-separated, whitespace-tolerant, and permissive when unset.

    The unset case matters most: it is what every existing developer machine
    and CI run hits, and it must not require anyone to learn this variable
    exists before the app will start.
    """
    if raw is None:
        monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    else:
        monkeypatch.setenv("ALLOWED_HOSTS", raw)

    assert main.allowed_hosts() == expected


# ---------------------------------------------------------------------------
# wiring
# ---------------------------------------------------------------------------
def test_the_app_registers_trusted_host_middleware():
    """The control is actually attached to the application.

    A middleware that parses its configuration perfectly and is never installed
    protects nothing, and that failure is invisible -- every test passes, every
    request succeeds, and the header stays forgeable. This is the assertion
    that a refactor of ``main``'s middleware stack cannot silently drop it.
    """
    installed = [m for m in main.app.user_middleware if m.cls is TrustedHostMiddleware]

    assert len(installed) == 1, (
        "TrustedHostMiddleware is not installed on the app; the Host header is "
        "unguarded and share URLs can be forged."
    )


def test_the_middleware_is_configured_from_the_environment():
    """It is wired to ``allowed_hosts()``, not to a hardcoded list."""
    installed = next(
        m for m in main.app.user_middleware if m.cls is TrustedHostMiddleware
    )
    options = dict(installed.kwargs)

    assert options["allowed_hosts"] == main.allowed_hosts()


# ---------------------------------------------------------------------------
# behaviour
# ---------------------------------------------------------------------------
def _guarded_app(hosts):
    """A minimal app carrying the same middleware, for behavioural assertions.

    Built fresh rather than reusing ``main.app``: the real app reads its
    configuration once at import, so asserting the *effect* of a non-default
    ``ALLOWED_HOSTS`` on it would mean reloading ``main`` mid-suite -- which
    re-runs its bootstrap and swaps the module every other test imported. This
    exercises the identical Starlette middleware with the identical
    configuration, which is what the behaviour actually depends on.
    """
    app = FastAPI()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.get("/probe")
    def probe(request_host: str = ""):  # pragma: no cover - trivial
        return {"ok": True}

    return app


def test_a_forged_host_is_rejected_before_any_handler_runs():
    """The attack, executed. ``Host: evil.example`` never reaches the route."""
    client = TestClient(_guarded_app(["mealplanner.app"]))

    response = client.get("/probe", headers={"Host": "evil.example"})

    assert response.status_code == 400
    assert "ok" not in response.text


def test_the_real_host_is_accepted():
    """The control must not break the deployment it is protecting."""
    client = TestClient(_guarded_app(["mealplanner.app"]))

    response = client.get("/probe", headers={"Host": "mealplanner.app"})

    assert response.status_code == 200


def test_the_permissive_default_accepts_anything():
    """What every developer machine and CI run experiences today.

    Asserted explicitly so that nobody "hardens" the default without noticing
    they have broken every unconfigured environment, and so the security
    posture of the default is written down as a *tested fact* rather than an
    assumption.
    """
    client = TestClient(_guarded_app(main.allowed_hosts()))

    response = client.get("/probe", headers={"Host": "anything.at.all"})

    assert response.status_code == 200


def test_a_forged_host_cannot_reach_share_url_construction(monkeypatch):
    """The end the control exists to protect, stated as the property it buys.

    With ``ALLOWED_HOSTS`` configured, the only ``Host`` values that reach a
    handler are the configured ones -- so the fallback in ``shares.share_url``
    can only ever produce a URL on a host the operator named. This asserts the
    fallback's output for an allowed host, and the middleware test above
    asserts that a disallowed one never gets that far; together they are the
    guarantee.
    """
    import shares

    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)

    class _Url:
        scheme = "https"
        netloc = "mealplanner.app"

    class _Request:
        url = _Url()

    url = shares.share_url("tok-123", _Request())

    assert url == "https://mealplanner.app/s/tok-123"


def test_public_base_url_still_wins_over_the_host_header(monkeypatch):
    """Belt and braces: configuring the base URL removes the question entirely.

    ``TrustedHostMiddleware`` is the control; ``PUBLIC_BASE_URL`` is the
    stronger, simpler answer where it can be set, and it must keep taking
    precedence so an operator who sets it is not silently relying on the
    allowlist as well.
    """
    import shares

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://canonical.example/")

    class _Url:
        scheme = "https"
        netloc = "mealplanner.app"

    class _Request:
        url = _Url()

    assert shares.share_url("tok", _Request()) == "https://canonical.example/s/tok"
