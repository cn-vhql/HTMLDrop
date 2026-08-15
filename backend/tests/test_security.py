"""Security helper unit tests."""
from __future__ import annotations

import base64

import pytest

from app.security import (
    PASSWORD_COOKIE_MAX_AGE,
    hash_ip,
    hash_password,
    make_slug,
    sign_password_cookie,
    verify_password,
    verify_password_cookie,
)


class TestPasswordHash:
    def test_roundtrip(self):
        encoded = hash_password("s3cret!")
        assert encoded.startswith("scrypt$")
        assert verify_password("s3cret!", encoded)

    def test_wrong_password(self):
        encoded = hash_password("right")
        assert not verify_password("wrong", encoded)

    def test_salt_is_random(self):
        assert hash_password("same") != hash_password("same")

    def test_corrupt_format(self):
        assert not verify_password("x", "not-a-hash")
        assert not verify_password("x", "scrypt$bad$bad$extra")
        assert not verify_password("x", "md5$aaa$bbb")

    def test_bad_base64(self):
        assert not verify_password("x", "scrypt$!!!$!!!")


class TestPasswordCookie:
    def test_roundtrip(self):
        value = sign_password_cookie("abc", "hash1")
        assert verify_password_cookie("abc", "hash1", value)

    def test_wrong_slug(self):
        value = sign_password_cookie("abc", "hash1")
        assert not verify_password_cookie("xyz", "hash1", value)

    def test_wrong_password_hash_fingerprint(self):
        value = sign_password_cookie("abc", "hash1")
        assert not verify_password_cookie("abc", "hash2", value)

    def test_tampered(self):
        value = sign_password_cookie("abc", "hash1")
        assert not verify_password_cookie("abc", "hash1", value[:-2] + "00")

    def test_empty(self):
        assert not verify_password_cookie("abc", "hash1", "")

    def test_expired(self, monkeypatch):
        import time as real_time

        value = sign_password_cookie("abc", "hash1")

        class FakeTime:
            @staticmethod
            def time():
                return real_time.time() + PASSWORD_COOKIE_MAX_AGE + 10

        monkeypatch.setattr("app.security.time", FakeTime)
        assert not verify_password_cookie("abc", "hash1", value)


class TestMisc:
    def test_hash_ip_deterministic(self):
        assert hash_ip("1.2.3.4") == hash_ip("1.2.3.4")
        assert hash_ip("1.2.3.4") != hash_ip("5.6.7.8")

    def test_slug_format(self):
        slug = make_slug()
        assert 8 <= len(slug) <= 12
        # url-safe base64 字符集
        assert set(slug) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")

    def test_slug_unique(self):
        assert make_slug() != make_slug()


def test_scrypt_uses_expected_params():
    encoded = hash_password("x")
    _, salt_b64, digest_b64 = encoded.split("$")
    salt = base64.urlsafe_b64decode(salt_b64.encode())
    digest = base64.urlsafe_b64decode(digest_b64.encode())
    assert len(salt) == 16
    assert len(digest) == 64  # sha256 输出
