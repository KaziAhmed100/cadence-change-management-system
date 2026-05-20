"""Unit tests for security primitives - password hashing and JWT helpers."""

from datetime import timedelta

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_then_verify_roundtrips(self) -> None:
        hashed = hash_password("hunter2")
        assert verify_password("hunter2", hashed) is True

    def test_verify_rejects_wrong_password(self) -> None:
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("nope", hashed) is False

    def test_two_hashes_of_same_password_differ(self) -> None:
        # Bcrypt includes a per-hash salt; same plaintext produces different
        # ciphertext on each call. Critical property for password security.
        h1 = hash_password("samepass")
        h2 = hash_password("samepass")
        assert h1 != h2
        # But both should still verify correctly
        assert verify_password("samepass", h1)
        assert verify_password("samepass", h2)


class TestJWT:
    def test_create_and_decode_roundtrips(self) -> None:
        token = create_access_token(subject="user-123", role="admin")
        decoded = decode_token(token)
        assert decoded["sub"] == "user-123"
        assert decoded["role"] == "admin"
        assert decoded["type"] == "access"

    def test_decode_rejects_tampered_token(self) -> None:
        token = create_access_token(subject="user-123", role="admin")
        # Flip a character in the signature portion to invalidate it
        tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
        with pytest.raises(JWTError):
            decode_token(tampered)

    def test_decode_rejects_expired_token(self) -> None:
        token = create_access_token(
            subject="user-123",
            role="admin",
            expires_delta=timedelta(seconds=-1),  # already expired
        )
        with pytest.raises(JWTError):
            decode_token(token)

    def test_decode_rejects_gibberish(self) -> None:
        with pytest.raises(JWTError):
            decode_token("this-is-not-a-jwt")
