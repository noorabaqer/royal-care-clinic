"""
accounts.py
===========
:class:`UserAccount` - the login account a patient creates to use the
patient portal (view appointments, update profile, download summaries).

Passwords are never stored in plain text: a random salt is generated and
the password is hashed with PBKDF2-HMAC-SHA256 from the standard library.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime
from typing import TYPE_CHECKING

from .exceptions import ValidationError

if TYPE_CHECKING:
    from .people import Person

MIN_PASSWORD_LENGTH = 8
_ITERATIONS = 100_000


class UserAccount:
    """Login credentials linked to one person (one-to-one association)."""

    def __init__(self, username: str, password: str, owner: Person) -> None:
        if len(username.strip()) < 3:
            raise ValidationError("Username must be at least 3 characters.")
        self._username = username.strip()
        self._salt = os.urandom(16)
        self._password_hash = self._hash(password)
        self.owner = owner
        self.created_at = datetime.now()
        self.is_active = True

    @property
    def username(self) -> str:
        return self._username

    # ------------------------------------------------------------------ #
    def _hash(self, password: str) -> bytes:
        """Validate the password and return its salted hash (private helper)."""
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        return hashlib.pbkdf2_hmac("sha256", password.encode(), self._salt, _ITERATIONS)

    def verify_password(self, password: str) -> bool:
        """Return True if ``password`` matches (constant-time comparison)."""
        if not self.is_active:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                        self._salt, _ITERATIONS)
        return hmac.compare_digest(candidate, self._password_hash)

    def change_password(self, old_password: str, new_password: str) -> None:
        """Change the password after confirming the old one."""
        if not self.verify_password(old_password):
            raise ValidationError("Current password is incorrect.")
        self._password_hash = self._hash(new_password)

    def __repr__(self) -> str:
        return f"UserAccount({self._username!r}, active={self.is_active})"
