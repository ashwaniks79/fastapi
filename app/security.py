# app/security.py
import os
import logging
from cryptography.fernet import Fernet, InvalidToken

_logger = logging.getLogger(__name__)

def _get_fernet():
    key = os.getenv("PENDING_PASSWORD_FERNET_KEY")
    if not key:
        # In production do not generate on the fly; fail early instead.
        _logger.error("PENDING_PASSWORD_FERNET_KEY not set. Set it in env.")
        raise RuntimeError("PENDING_PASSWORD_FERNET_KEY not configured")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)

def encrypt_password(plain_password: str) -> str:
    f = _get_fernet()
    token = f.encrypt(plain_password.encode())
    return token.decode()

def decrypt_password(token_str: str) -> str:
    f = _get_fernet()
    try:
        return f.decrypt(token_str.encode()).decode()
    except InvalidToken:
        _logger.error("Failed to decrypt pending password - invalid token")
        raise
