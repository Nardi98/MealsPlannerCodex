"""Unit tests for auth-related Pydantic schemas (no DB required)."""
import pytest
from pydantic import ValidationError

from schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserOut,
    VerifyEmailRequest,
    validate_password,
)


VALID_PW = "Abcdef12"


# --- validate_password helper -------------------------------------------------

def test_validate_password_accepts_valid():
    assert validate_password(VALID_PW) == VALID_PW


def test_validate_password_rejects_missing_upper():
    with pytest.raises(ValueError):
        validate_password("abcdef12")


def test_validate_password_rejects_missing_lower():
    with pytest.raises(ValueError):
        validate_password("ABCDEF12")


def test_validate_password_rejects_missing_digit():
    with pytest.raises(ValueError):
        validate_password("Abcdefgh")


def test_validate_password_rejects_too_short():
    with pytest.raises(ValueError):
        validate_password("Abc123")  # 6 chars


def test_validate_password_accepts_72_bytes_boundary():
    # 72 ASCII bytes, includes upper/lower/digit.
    pw = "Aa1" + ("x" * 69)
    assert len(pw.encode("utf-8")) == 72
    assert validate_password(pw) == pw


def test_validate_password_rejects_73_bytes():
    pw = "Aa1" + ("x" * 70)
    assert len(pw.encode("utf-8")) == 73
    with pytest.raises(ValueError):
        validate_password(pw)


def test_validate_password_counts_bytes_not_chars():
    # Each 'e' with acute accent is 2 bytes in UTF-8.
    # 3 ASCII prefix + 35 * 2-byte chars = 3 + 70 = 73 bytes, but only 38 chars.
    pw = "Aa1" + ("é" * 35)
    assert len(pw) == 38
    assert len(pw.encode("utf-8")) == 73
    with pytest.raises(ValueError):
        validate_password(pw)


# --- UserCreate ---------------------------------------------------------------

def test_user_create_valid():
    m = UserCreate(email="user@example.com", password=VALID_PW, display_name="Al")
    assert m.email == "user@example.com"
    assert m.display_name == "Al"


def test_user_create_display_name_optional():
    m = UserCreate(email="user@example.com", password=VALID_PW)
    assert m.display_name is None


def test_user_create_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password=VALID_PW)


def test_user_create_rejects_weak_password():
    with pytest.raises(ValidationError):
        UserCreate(email="user@example.com", password="weak")


# --- LoginRequest -------------------------------------------------------------

def test_login_request_valid():
    m = LoginRequest(email="user@example.com", password="anything")
    assert m.email == "user@example.com"


def test_login_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        LoginRequest(email="nope", password="anything")


# --- Token --------------------------------------------------------------------

def test_token_defaults_to_bearer():
    t = Token(access_token="xyz")
    assert t.token_type == "bearer"


# --- ForgotPasswordRequest ----------------------------------------------------

def test_forgot_password_request_valid():
    m = ForgotPasswordRequest(email="user@example.com")
    assert m.email == "user@example.com"


def test_forgot_password_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        ForgotPasswordRequest(email="bad")


# --- ResetPasswordRequest -----------------------------------------------------

def test_reset_password_request_valid():
    m = ResetPasswordRequest(token="tok", new_password=VALID_PW)
    assert m.new_password == VALID_PW


def test_reset_password_request_rejects_weak_password():
    with pytest.raises(ValidationError):
        ResetPasswordRequest(token="tok", new_password="weak")


# --- VerifyEmailRequest -------------------------------------------------------

def test_verify_email_request_valid():
    m = VerifyEmailRequest(token="tok")
    assert m.token == "tok"


# --- UserOut ------------------------------------------------------------------

def test_user_out_has_email_verified():
    m = UserOut(
        id=1,
        email="user@example.com",
        auth_provider="local",
        default_people=2,
        email_verified=True,
    )
    assert m.email_verified is True
