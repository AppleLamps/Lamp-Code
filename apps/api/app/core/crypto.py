import base64
import os
from typing import Optional
from cryptography.fernet import Fernet


class SecretBox:
    def __init__(self, key: Optional[str] = None) -> None:
        # Expect a base64 urlsafe key. If none provided, derive from env or generate (dev only)
        key = key or os.getenv("ENCRYPTION_KEY")
        environment = os.getenv("ENVIRONMENT", "development")

        if key is None:
            if environment == "production":
                raise ValueError(
                    "ENCRYPTION_KEY environment variable is required in production. "
                    "Generate a secure key with: python -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'"
                )
            else:
                # Dev fallback: generate ephemeral key (warn user)
                key = base64.urlsafe_b64encode(os.urandom(32)).decode()
                try:
                    from app.core.terminal_ui import ui
                    ui.warn("Using ephemeral encryption key in development. Encrypted data will not persist across restarts.", "Crypto")
                except Exception:
                    pass

        try:
            self._fernet = Fernet(key)
        except Exception as e:
            raise ValueError(f"Invalid encryption key format: {e}. Key must be a valid Fernet key.")

    def encrypt(self, plaintext: str) -> str:
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


secret_box = SecretBox()
