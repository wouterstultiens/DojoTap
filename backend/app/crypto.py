from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class TokenCipher:
    def __init__(self, passphrase: str):
        normalized = passphrase.strip() or "dojotap-dev-only-key"
        digest = hashlib.sha256(normalized.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str | None) -> str | None:
        value = (plaintext or "").strip()
        if not value:
            return None
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str | None) -> str | None:
        value = (ciphertext or "").strip()
        if not value:
            return None
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError):
            return None
