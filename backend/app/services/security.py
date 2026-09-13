import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger(__name__)

_encryption: "CredentialEncryption | None" = None


class CredentialEncryption:
    def __init__(self) -> None:
        key = get_settings().credentials_encryption_key
        if not key:
            raise RuntimeError(
                "CREDENTIALS_ENCRYPTION_KEY is required. "
                'Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, data: str) -> str:
        return self._fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt data") from exc

    def encrypt_tokens(self, tokens: dict) -> str:
        import json

        return self.encrypt(json.dumps(tokens))

    def decrypt_tokens(self, encrypted: str) -> dict:
        import json

        return json.loads(self.decrypt(encrypted))


def get_credential_encryption() -> CredentialEncryption:
    global _encryption
    if _encryption is None:
        _encryption = CredentialEncryption()
    return _encryption
