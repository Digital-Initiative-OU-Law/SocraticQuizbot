import os
import base64
from typing import Optional

try:
    from cryptography.fernet import Fernet
except Exception:  # cryptography may be missing in some environments
    Fernet = None  # type: ignore


class CryptoService:
    """Fernet-based encryption helper using FERNET_KEY_B64 from env.

    If the key or cryptography is unavailable, encrypt/decrypt become no-ops
    and the caller can store/read plaintext safely.
    """

    def __init__(self):
        key_b64 = os.getenv("FERNET_KEY_B64")
        self._enabled = bool(key_b64 and Fernet is not None)
        self._fernet: Optional[Fernet] = None
        if self._enabled:
            try:
                # Validate/normalize the key
                base64.urlsafe_b64decode(key_b64)
                self._fernet = Fernet(key_b64)
            except Exception:
                # Invalid key; disable encryption
                self._enabled = False
                self._fernet = None

    def is_enabled(self) -> bool:
        return self._enabled and self._fernet is not None

    def encrypt(self, data: str) -> Optional[bytes]:
        if not self.is_enabled() or not data:
            return None
        return self._fernet.encrypt(data.encode("utf-8"))  # type: ignore[arg-type]

    def decrypt(self, blob: Optional[bytes]) -> Optional[str]:
        if not self.is_enabled() or not blob:
            return None
        try:
            return self._fernet.decrypt(blob).decode("utf-8")  # type: ignore[arg-type]
        except Exception:
            return None

