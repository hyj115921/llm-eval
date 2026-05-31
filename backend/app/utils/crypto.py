"""
API Key 加密存储 — 使用 Fernet 对称加密。
生产环境应使用环境变量 JWT_SECRET_KEY 派生 Fernet key。
"""
import base64
import os
from cryptography.fernet import Fernet

from app.core.config import settings


def _get_fernet() -> Fernet:
    """从 JWT_SECRET_KEY 派生 Fernet 密钥"""
    key_material = settings.JWT_SECRET_KEY.encode()
    # Fernet 需要 32 字节的 base64-urlsafe 编码密钥
    # 将 JWT_SECRET_KEY 填充到 32 字节后 base64 编码
    padded = key_material.ljust(32, b"\x00")[:32]
    fernet_key = base64.urlsafe_b64encode(padded)
    return Fernet(fernet_key)


_fernet = None


def _ensure_fernet():
    global _fernet
    if _fernet is None:
        try:
            _fernet = _get_fernet()
        except ImportError:
            _fernet = None


def encrypt_api_key(plaintext: str) -> str:
    """加密 API Key"""
    if not plaintext:
        return ""
    _ensure_fernet()
    if _fernet is None:
        return plaintext  # cryptography 不可用时回退明文（开发环境）
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """解密 API Key"""
    if not ciphertext:
        return ""
    _ensure_fernet()
    if _fernet is None:
        return ciphertext
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except Exception:
        # 可能是旧明文数据
        return ciphertext
