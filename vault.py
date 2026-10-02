"""
vault.py
--------
The internal password vault. Unlike user login passwords (auth.py, which
uses irreversible hashing), vault passwords must be recoverable by the
user later -- so we use symmetric ENCRYPTION (Fernet, from the
`cryptography` library) instead of hashing.

Fernet is authenticated symmetric encryption: the same key encrypts and
decrypts, and it detects tampering. The key lives in vault.key on disk --
in a real product this would be in a secrets manager / KMS, not a plain
file, but that's out of scope for this project.

Key design point for the "Password Reset" ticket flow:
- Staff can trigger `reset_vault_password()`, which generates a brand new
  password and stores it ENCRYPTED. Staff get back only a success flag --
  never the plaintext. The affected VaultEntry is flagged `reset_pending`.
- Only the owning user can later call `claim_reset()`, which decrypts and
  reveals the new password to them (once), then clears the flag.
"""

import os
import secrets
import string
from datetime import datetime

from cryptography.fernet import Fernet

from storage import load_json, save_json

VAULT_FILE = "vault.json"
KEY_FILE = "vault.key"


# ---------------------------------------------------------------------
# Encryption key setup
# ---------------------------------------------------------------------
def _load_or_create_key() -> bytes:
    """Load the Fernet key from disk, generating one on first run.
    Every VaultEntry is encrypted/decrypted with this single key."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()

    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    return key


_fernet = Fernet(_load_or_create_key())


def encrypt_password(plain: str) -> str:
    return _fernet.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_password(token: str) -> str:
    return _fernet.decrypt(token.encode("utf-8")).decode("utf-8")


# ---------------------------------------------------------------------
# Password generation
# ---------------------------------------------------------------------
def generate_strong_password(length: int = 16) -> str:
    """Cryptographically-secure random password (uses `secrets`, not
    `random`, since this is security-sensitive)."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------
# Vault storage: { user_id: [ {service_name, encrypted_password,
#                              last_updated, reset_pending}, ... ] }
# ---------------------------------------------------------------------
def load_vault():
    return load_json(VAULT_FILE, {})


def save_vault(vault):
    save_json(VAULT_FILE, vault)


def get_user_entries(user_id: str):
    vault = load_vault()
    return vault.get(user_id, [])


def add_vault_entry(user_id: str, service_name: str, plain_password: str):
    """User adds a new saved password (manual or auto-generated)."""
    vault = load_vault()
    entries = vault.setdefault(user_id, [])

    for e in entries:
        if e["service_name"].lower() == service_name.lower():
            return False, "You already have an entry for this service."

    entries.append({
        "service_name": service_name,
        "encrypted_password": encrypt_password(plain_password),
        "last_updated": datetime.now().isoformat(timespec="seconds"),
        "reset_pending": False,
    })
    save_vault(vault)
    return True, "Vault entry saved."


def reset_vault_password(user_id: str, service_name: str) -> bool:
    """
    Called ONLY from the staff resolution flow (tickets.py) when a
    "Password Reset" ticket is resolved.

    Generates a new random password, encrypts it, stores it, and flags
    reset_pending=True so the user can claim it. The plaintext is never
    returned to the caller -- staff literally cannot see it, by design.
    """
    vault = load_vault()
    entries = vault.setdefault(user_id, [])

    entry = None
    for e in entries:
        if e["service_name"].lower() == service_name.lower():
            entry = e
            break

    if entry is None:
        # User requested a reset for a service that has no vault entry
        # yet -- create one so the reset still has somewhere to land.
        entry = {
            "service_name": service_name,
            "encrypted_password": "",
            "last_updated": "",
            "reset_pending": False,
        }
        entries.append(entry)

    new_password = generate_strong_password()
    entry["encrypted_password"] = encrypt_password(new_password)
    entry["last_updated"] = datetime.now().isoformat(timespec="seconds")
    entry["reset_pending"] = True

    save_vault(vault)
    return True  # intentionally NOT returning new_password to the caller


def claim_reset(user_id: str, service_name: str):
    """
    Called from the USER side. If a reset is pending for this service,
    decrypt and return the new plaintext password ONCE, then clear the
    pending flag. Returns None if there's nothing to claim.
    """
    vault = load_vault()
    entries = vault.get(user_id, [])

    for e in entries:
        if e["service_name"].lower() == service_name.lower() and e.get("reset_pending"):
            plain = decrypt_password(e["encrypted_password"])
            e["reset_pending"] = False
            save_vault(vault)
            return plain

    return None
