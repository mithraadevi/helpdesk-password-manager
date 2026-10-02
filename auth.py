"""
auth.py
-------
Handles both roles' identity:

- User accounts: password is HASHED (hashlib.sha256) with a unique random
  salt per user. We never store or recover the plaintext password -- login
  works by re-hashing the attempt with the stored salt and comparing hashes.
  This is one-way (irreversible) by design.

- Staff accounts: intentionally simple, ID-only lookup (per spec: "no need
  for full security"). Staff are internal/trusted users in this system.

Contrast this with vault.py, where *vault* passwords are ENCRYPTED (Fernet,
reversible) rather than hashed, because the whole point of a password vault
is that the plaintext must be retrievable later.
"""

import hashlib
import secrets
import uuid

from storage import load_json, save_json

USERS_FILE = "users.json"
STAFF_FILE = "staff.json"


# ---------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------
def _hash_password(password: str, salt: str) -> str:
    """SHA-256 hash of (salt + password). Salting prevents identical
    passwords from producing identical hashes, and defeats precomputed
    rainbow-table attacks."""
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------
def load_users():
    return load_json(USERS_FILE, {})


def save_users(users):
    save_json(USERS_FILE, users)


def register_user(name: str, password: str) -> str:
    """Create a new user record and persist it immediately. Returns the
    new user_id so it can be shown to the person registering."""
    users = load_users()

    user_id = str(uuid.uuid4())[:8]
    salt = secrets.token_hex(16)               # unique random salt per user
    hashed = _hash_password(password, salt)

    users[user_id] = {
        "user_id": user_id,
        "name": name,
        "hashed_password": hashed,
        "salt": salt,
    }
    save_users(users)
    return user_id


def login_user(user_id: str, password: str):
    """
    Returns (success: bool, message_or_name: str).
    On success, message_or_name is the user's display name.
    On failure, it's a human-readable error message.
    """
    users = load_users()

    if user_id not in users:
        return False, "User ID not found."

    record = users[user_id]
    attempt_hash = _hash_password(password, record["salt"])

    if attempt_hash == record["hashed_password"]:
        return True, record["name"]
    return False, "Incorrect password."


# ---------------------------------------------------------------------
# Staff
# ---------------------------------------------------------------------
def load_staff():
    return load_json(STAFF_FILE, {})


def save_staff(staff):
    save_json(STAFF_FILE, staff)


def register_staff(name: str) -> str:
    staff = load_staff()
    staff_id = str(uuid.uuid4())[:8]
    staff[staff_id] = {
        "staff_id": staff_id,
        "name": name,
        "available": True,
    }
    save_staff(staff)
    return staff_id


def login_staff(staff_id: str):
    """Simple ID-only check, as specified (no password for staff)."""
    staff = load_staff()
    if staff_id not in staff:
        return False, "Staff ID not found."
    return True, staff[staff_id]["name"]
