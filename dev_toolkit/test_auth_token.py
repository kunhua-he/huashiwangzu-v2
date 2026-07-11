from pathlib import Path

from dev_toolkit import auth_token


def test_encode_hs256_builds_three_part_jwt() -> None:
    token = auth_token._encode_hs256({"sub": "1", "role": "admin", "sv": 2, "exp": 999}, "secret")

    assert len(token.split(".")) == 3


def test_account_for_role_falls_back_to_admin() -> None:
    accounts = {"admin": {"user_id": 1, "role": "admin"}}

    assert auth_token._account_for_role(accounts, "viewer") == {"user_id": 1, "role": "admin"}


def test_backend_jwt_settings_reads_env_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_ALGORITHM", raising=False)
    monkeypatch.delenv("JWT_EXPIRE_MINUTES", raising=False)
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / ".env").write_text(
        "JWT_SECRET=local-secret\nJWT_ALGORITHM=HS256\nJWT_EXPIRE_MINUTES=30\n",
        encoding="utf-8",
    )

    assert auth_token._backend_jwt_settings(tmp_path) == ("local-secret", "HS256", 30)
