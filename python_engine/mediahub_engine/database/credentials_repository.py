"""Encrypted provider credentials store (Phase 6).

Credentials (passwords, tokens) are encrypted at rest using a simple
XOR-based cipher keyed off the engine's work_dir path. In a production
Android build, this is backed by Android Keystore; the Python engine's
encryption is a fallback for non-Android environments.

The [CredentialsRepository] stores [Credential] objects per provider and
the [DownloadManager] / providers consult it via the credential store
protocol from Phase 2.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time

from mediahub_engine.database.connection import Database
from mediahub_engine.providers.base import Credential
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class CredentialsRepository:
    """SQLite-backed, encrypted provider credentials."""

    def __init__(self, db: Database, *, encryption_key: bytes | None = None) -> None:
        self._db = db
        if encryption_key is not None:
            self._key = encryption_key
        else:
            # Derive a stable key from the DB path (production uses Android Keystore).
            self._key = hashlib.sha256(str(db.path).encode()).digest()

    def set(self, provider: str, credential: Credential) -> None:
        self._db.execute(
            """
            INSERT INTO credentials (
                provider, username, password, cookies_path, session_path,
                token, extra, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider) DO UPDATE SET
                username=excluded.username,
                password=excluded.password,
                cookies_path=excluded.cookies_path,
                session_path=excluded.session_path,
                token=excluded.token,
                extra=excluded.extra,
                updated_at=excluded.updated_at
            """,
            (
                provider,
                credential.username,
                _encrypt(self._key, credential.password) if credential.password else None,
                credential.cookies_path,
                credential.session_path,
                _encrypt(self._key, credential.token) if credential.token else None,
                json.dumps(credential.extra, default=str),
                time.time(),
            ),
        )

    def get(self, provider: str) -> Credential | None:
        row = self._db.query_one("SELECT * FROM credentials WHERE provider = ?", (provider,))
        if row is None:
            return None
        return _row_to_credential(self._key, row)

    def list_providers(self) -> list[str]:
        rows = self._db.query_all("SELECT provider FROM credentials ORDER BY provider")
        return [r["provider"] for r in rows]

    def delete(self, provider: str) -> bool:
        cur = self._db.execute("DELETE FROM credentials WHERE provider = ?", (provider,))
        return cur.rowcount > 0

    def has(self, provider: str) -> bool:
        row = self._db.query_one("SELECT 1 FROM credentials WHERE provider = ?", (provider,))
        return row is not None


# ---------------------------------------------------------------------------
# Encryption helpers (XOR-stream cipher — Android Keystore replaces this)
# ---------------------------------------------------------------------------


def _encrypt(key: bytes, plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    raw = plaintext.encode("utf-8")
    cipher = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    return base64.b64encode(cipher).decode("ascii")


def _decrypt(key: bytes, ciphertext: str | None) -> str | None:
    if ciphertext is None:
        return None
    try:
        cipher = base64.b64decode(ciphertext)
        plain = bytes(b ^ key[i % len(key)] for i, b in enumerate(cipher))
        return plain.decode("utf-8")
    except Exception:
        log.warning("failed to decrypt credential value")
        return None


def _row_to_credential(key: bytes, row) -> Credential:  # type: ignore[no-untyped-def]
    extra_raw = row["extra"]
    try:
        extra = json.loads(extra_raw) if extra_raw else {}
    except (json.JSONDecodeError, TypeError):
        extra = {}
    return Credential(
        username=row["username"],
        password=_decrypt(key, row["password"]),
        cookies_path=row["cookies_path"],
        session_path=row["session_path"],
        token=_decrypt(key, row["token"]),
        extra=extra,
    )


__all__ = ["CredentialsRepository"]
