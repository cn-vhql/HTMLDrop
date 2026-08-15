from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import time


# 未显式配置时生成随机密钥：避免硬编码默认值导致会话可伪造。
# 注意：随机密钥在每次重启后都会变化，已有会话与 IP 统计哈希会全部失效。
SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(48)
if os.getenv("SESSION_SECRET") is None:
    logging.warning("未设置 SESSION_SECRET，已生成随机密钥；重启后所有会话与 IP 统计哈希将失效，请通过环境变量固定该值")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_text, digest_text = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def hash_ip(ip: str) -> str:
    return hmac.new(SESSION_SECRET.encode(), ip.encode(), hashlib.sha256).hexdigest()


PASSWORD_COOKIE_MAX_AGE = 30 * 24 * 3600


def sign_password_cookie(slug: str, password_hash: str) -> str:
    """为已通过密码验证的访问签发 cookie 值：slug|密码指纹|过期时间|签名。"""
    fingerprint = hashlib.sha256(password_hash.encode()).hexdigest()[:16]
    expiry = int(time.time()) + PASSWORD_COOKIE_MAX_AGE
    payload = f"{slug}|{fingerprint}|{expiry}"
    digest = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{digest}"


def verify_password_cookie(slug: str, password_hash: str, value: str) -> bool:
    """校验密码访问 cookie；管理员改密后指纹不匹配，旧 cookie 立即失效。"""
    try:
        payload, digest = value.rsplit("|", 1)
        expected = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(digest, expected):
            return False
        cookie_slug, fingerprint, expiry = payload.split("|", 2)
        if cookie_slug != slug:
            return False
        if fingerprint != hashlib.sha256(password_hash.encode()).hexdigest()[:16]:
            return False
        if int(expiry) < int(time.time()):
            return False
    except (ValueError, TypeError):
        return False
    return True


def make_slug() -> str:
    return secrets.token_urlsafe(7)

