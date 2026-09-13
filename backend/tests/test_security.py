import pytest
from cryptography.fernet import Fernet

from app.api.deps import create_access_token, decode_access_token, verify_telegram_widget_auth


@pytest.fixture
def encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", key)
    monkeypatch.setenv("INTERNAL_BOT_SECRET", "test-secret-key-for-jwt-signing!!")
    return key


def test_credential_encryption_roundtrip(encryption_key):
    from importlib import reload

    import app.services.security as security_mod

    reload(security_mod)
    security_mod._encryption = None
    enc = security_mod.get_credential_encryption()
    tokens = {"access_token": "abc", "refresh_token": "xyz"}
    encrypted = enc.encrypt_tokens(tokens)
    assert enc.decrypt_tokens(encrypted) == tokens


def test_jwt_roundtrip(encryption_key, monkeypatch):
    monkeypatch.setenv("INTERNAL_BOT_SECRET", "test-secret-key-for-jwt-signing!!")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-32-characters-min!!")
    from importlib import reload

    import app.config as config_mod

    reload(config_mod)
    config_mod.get_settings.cache_clear()

    from importlib import reload as r2

    import app.api.deps as deps_mod

    r2(deps_mod)

    token = deps_mod.create_access_token(12345)
    assert deps_mod.decode_access_token(token) == 12345


def test_telegram_widget_auth():
    bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    auth_data = {
        "id": 12345,
        "first_name": "Test",
        "auth_date": 1700000000,
        "hash": "invalid",
    }
    assert verify_telegram_widget_auth(auth_data.copy(), bot_token) is False
