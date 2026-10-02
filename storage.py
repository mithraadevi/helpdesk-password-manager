"""
storage.py
----------
Generic JSON persistence helpers used by every other module.

Why this exists as its own file:
- Keeps "how do we read/write a JSON file safely" in ONE place.
- Every data file (users.json, staff.json, tickets.json, vault.json) goes
  through the same two functions, so error handling is consistent everywhere.
"""

import json
import os


def load_json(filepath, default):
    """
    Load a JSON file and return its contents.

    - If the file does not exist yet -> return `default` (e.g. {} or []).
      This covers "first run, no data yet".
    - If the file exists but is corrupted / not valid JSON -> also return
      `default` instead of crashing the app. We print a warning so it's
      visible in the terminal/logs, but the Streamlit app keeps running.
    """
    if not os.path.exists(filepath):
        return default

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, OSError, ValueError) as e:
        print(f"[storage] WARNING: could not read '{filepath}' ({e}). "
              f"Starting from an empty default instead of crashing.")
        return default


def save_json(filepath, data):
    """
    Write `data` to `filepath` as JSON immediately.

    Called right after every create/update so data is never held only in
    memory. Returns True/False so callers can decide whether to show an
    error to the user if the disk write itself fails (e.g. permissions).
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except OSError as e:
        print(f"[storage] ERROR: could not write '{filepath}' ({e}).")
        return False
