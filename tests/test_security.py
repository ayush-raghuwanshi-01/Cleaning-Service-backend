from uuid import uuid4

from app.core.security import create_token, decode_token, hash_password, verify_password


def test_argon2_hashes_and_verifies_password() -> None:
    password_hash = hash_password("A-long-test-password-123")
    assert password_hash != "A-long-test-password-123"
    assert verify_password("A-long-test-password-123", password_hash)


def test_token_requires_expected_type() -> None:
    token = create_token(uuid4(), "access", __import__("datetime").timedelta(minutes=1), "a" * 32)
    assert decode_token(token, "access", "a" * 32)
