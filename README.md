# Help Desk + Password Manager

A Streamlit help-desk ticketing system where "Password Reset" tickets are linked to an internal, encrypted password vault.

## Run it

```bash
pip install -r requirements.txt
streamlit run main.py
```

On first launch there's no data yet — use the **Register** tab (under both User and Staff login) to create accounts. Save the generated IDs; they're your login credentials.

## File map

| File | Responsibility |
|---|---|
| `storage.py` | Generic JSON load/save, with graceful handling of missing/corrupted files |
| `auth.py` | User accounts (hashed + salted passwords via `hashlib`) and Staff accounts (simple ID lookup) |
| `vault.py` | The password vault — passwords are **encrypted** (reversible, via `cryptography`'s Fernet), not hashed, because they must be recoverable |
| `tickets.py` | Ticket CRUD, FIFO auto-assignment, resolution (incl. triggering vault resets), analytics |
| `main.py` | Streamlit UI + routing only — no business logic lives here |

## Key design points (for viva)

- **Hashing vs. encryption**: user login passwords are hashed one-way (`auth.py`) — never recoverable, only re-checkable. Vault passwords are encrypted two-way (`vault.py`) — must be recoverable by the owning user. This is the core crypto distinction the whole app is built around.
- **Salting**: each user gets a unique random salt (`secrets.token_hex`) stored alongside their hash, so identical passwords across users produce different hashes and rainbow tables don't work.
- **Password Reset ↔ Vault link**: when a user submits a "Password Reset" ticket, the description field holds the *service name*. When staff resolve that ticket, `tickets.resolve_ticket()` calls `vault.reset_vault_password()`, which generates + encrypts a new password and flags the entry `reset_pending`. Staff only get a success/fail boolean back — the plaintext never reaches them. The user later calls `claim_reset()` to decrypt and view it once.
- **FIFO auto-assignment**: open tickets are sorted by `created_at`; the first staff member with `available == True` (in dict order) gets the oldest ticket.
- **Persistence**: every create/update calls `save_json()` immediately — nothing is buffered only in memory. `load_json()` catches missing files and `JSONDecodeError` and falls back to an empty default instead of crashing.
- **Data files** (`users.json`, `staff.json`, `tickets.json`, `vault.json`, `vault.key`) are created automatically on first run in the working directory.
