"""API Key 加密：Fernet 对称加密，主密钥来自环境变量 AI_KEY_SECRET。

部署要求：本地 .env 中设置 AI_KEY_SECRET（任意 32 字节 base64，
可用 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成）。
未设置时用开发默认值（仅本机自用可接受，多人/公网部署必须设置）。
"""
import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

_ENV_KEY = "AI_KEY_SECRET"


def _fernet() -> Fernet:
    raw = os.environ.get(_ENV_KEY, "").strip()
    if raw:
        # 允许直接给 Fernet key，或任意口令（做 SHA256 派生）
        try:
            return Fernet(raw.encode())
        except Exception:
            digest = hashlib.sha256(raw.encode()).digest()
            return Fernet(base64.urlsafe_b64encode(digest))
    # 开发默认：机器内固定派生，仅防明文落盘
    digest = hashlib.sha256(b"muse-ai-local-dev-key").digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_key(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_key(cipher: str) -> str:
    if not cipher:
        return ""
    try:
        return _fernet().decrypt(cipher.encode()).decode()
    except InvalidToken:
        return ""


def mask_key(plain_or_cipher: str, is_cipher: bool = True) -> str:
    """脱敏展示：sk-****abcd"""
    raw = decrypt_key(plain_or_cipher) if is_cipher else plain_or_cipher
    if not raw:
        return ""
    if len(raw) <= 8:
        return "****"
    return f"{raw[:3]}-****{raw[-4:]}"
