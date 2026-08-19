"""D-8: the per-user rate-limit key and the second limiter.

SH-11, CP-9, and UN-7 say "per user"; the existing ``/auth/*`` limiter is
IP-keyed and must keep working exactly as it does.
"""

import os
from types import SimpleNamespace

import auth_users
import ratelimit


def _request(*, authorization=None, host="203.0.113.9"):
    """A stand-in carrying only what ``user_or_ip_key`` reads."""
    headers = {}
    if authorization is not None:
        headers["authorization"] = authorization
    return SimpleNamespace(
        headers=headers,
        client=SimpleNamespace(host=host),
        scope={"type": "http", "client": (host, 1234), "headers": []},
    )


def test_falls_back_to_the_client_address_without_a_token():
    assert ratelimit.user_or_ip_key(_request()) == "203.0.113.9"


def test_keys_on_the_subject_of_a_valid_bearer_token():
    token = auth_users.create_access_token("42")
    key = ratelimit.user_or_ip_key(_request(authorization=f"Bearer {token}"))
    assert key == "user:42"


def test_two_users_from_one_address_get_separate_keys():
    a = auth_users.create_access_token("1")
    b = auth_users.create_access_token("2")
    assert ratelimit.user_or_ip_key(
        _request(authorization=f"Bearer {a}")
    ) != ratelimit.user_or_ip_key(_request(authorization=f"Bearer {b}"))


def test_a_garbage_token_falls_back_rather_than_raising():
    key = ratelimit.user_or_ip_key(_request(authorization="Bearer not-a-jwt"))
    assert key == "203.0.113.9"


def test_a_non_bearer_scheme_falls_back():
    assert ratelimit.user_or_ip_key(
        _request(authorization="Basic dXNlcjpwYXNz")
    ) == "203.0.113.9"


def test_the_limits_are_configurable_with_documented_defaults():
    assert ratelimit.SHARE_RATE_LIMIT
    assert ratelimit.COPY_RATE_LIMIT
    assert ratelimit.USERNAME_CHECK_RATE_LIMIT


def test_the_limiter_honours_rate_limit_enabled():
    """The suite sets ``RATE_LIMIT_ENABLED=0``; the new limiter must obey it."""
    assert os.environ["RATE_LIMIT_ENABLED"] == "0"
    assert ratelimit.limiter.enabled is False


def test_the_second_limiter_is_distinct_from_the_auth_limiter():
    import main

    assert ratelimit.limiter is not main.limiter
    assert main.limiter.enabled is False
