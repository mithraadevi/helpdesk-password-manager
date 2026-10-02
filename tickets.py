"""
tickets.py
----------
Ticket lifecycle: create -> auto-assign (FIFO) -> resolve -> (analytics).

Design note on Password Reset tickets:
For this project, when a user submits a "Password Reset" ticket, the
description field is used to capture WHICH service the reset is for
(e.g. "Gmail"). That string is what links the ticket to a VaultEntry
when staff resolve it -- see resolve_ticket() below, which calls into
vault.reset_vault_password(user_id, description).
"""

import uuid
from datetime import datetime

from storage import load_json, save_json
from vault import reset_vault_password

TICKETS_FILE = "tickets.json"

# Status constants -- used instead of raw strings throughout, so a typo
# becomes a NameError instead of a silent bug.
STATUS_OPEN = "Open (Unassigned)"
STATUS_IN_PROGRESS = "In Progress"
STATUS_RESOLVED = "Resolved"

CATEGORIES = ["General", "Password Reset"]


def load_tickets():
    return load_json(TICKETS_FILE, [])


def save_tickets(tickets):
    save_json(TICKETS_FILE, tickets)


# ---------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------
def create_ticket(user_id: str, category: str, description: str) -> dict:
    tickets = load_tickets()

    ticket = {
        "ticket_id": str(uuid.uuid4()),        # full UUID4 stored; UI shows first 8 chars
        "user_id": user_id,
        "category": category,
        "description": description,
        "status": STATUS_OPEN,
        "assigned_to": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "assigned_at": None,
        "resolved_at": None,
    }

    tickets.append(ticket)
    save_tickets(tickets)                      # write immediately, not on exit
    return ticket


# ---------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------
def get_user_tickets(user_id: str):
    return [t for t in load_tickets() if t["user_id"] == user_id]


def get_ticket_by_id(ticket_id: str):
    for t in load_tickets():
        if t["ticket_id"] == ticket_id:
            return t
    return None


def get_tickets_assigned_to(staff_id: str):
    """Tickets currently 'In Progress' and assigned to this staff member --
    i.e. the ones they're allowed to resolve."""
    return [
        t for t in load_tickets()
        if t["assigned_to"] == staff_id and t["status"] == STATUS_IN_PROGRESS
    ]


# ---------------------------------------------------------------------
# Auto-assignment (FIFO)
# ---------------------------------------------------------------------
def auto_assign(staff_dict: dict, save_staff_fn):
    """
    FIFO assignment:
      1. Find the OLDEST ticket with status == Open (Unassigned).
      2. Find the FIRST staff member (in dict iteration order) with
         available == True.
      3. Assign: set assigned_to, assigned_at, status -> In Progress.

    Returns (success: bool, message: str). Never raises -- if there's
    nothing to assign or nobody available, it returns a clear message
    instead of crashing.
    """
    tickets = load_tickets()
    open_tickets = [t for t in tickets if t["status"] == STATUS_OPEN]

    if not open_tickets:
        return False, "No open tickets to assign."

    # Oldest first = FIFO
    open_tickets.sort(key=lambda t: t["created_at"])
    oldest = open_tickets[0]

    available_staff_id = None
    for staff_id, info in staff_dict.items():
        if info.get("available"):
            available_staff_id = staff_id
            break

    if available_staff_id is None:
        return False, "No staff available right now. Try again once someone is free."

    # Find and mutate the same ticket in the full list, then save.
    for t in tickets:
        if t["ticket_id"] == oldest["ticket_id"]:
            t["assigned_to"] = available_staff_id
            t["assigned_at"] = datetime.now().isoformat(timespec="seconds")
            t["status"] = STATUS_IN_PROGRESS
            break

    save_tickets(tickets)
    staff_name = staff_dict[available_staff_id]["name"]
    return True, f"Ticket {oldest['ticket_id'][:8]} assigned to {staff_name} ({available_staff_id})."


# ---------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------
def resolve_ticket(ticket_id: str, staff_id: str):
    """
    Resolve a ticket. Enforces that:
      - the ticket exists
      - it is assigned to THIS staff member (can't resolve someone else's)
      - it is currently In Progress (can't resolve twice)

    If the ticket's category is "Password Reset", automatically triggers
    a vault password reset for the ticket's owner. Staff never see the
    new plaintext password -- reset_vault_password() only returns a bool.
    """
    tickets = load_tickets()
    target = next((t for t in tickets if t["ticket_id"] == ticket_id), None)

    if target is None:
        return False, "Ticket not found."
    if target["assigned_to"] != staff_id:
        return False, "This ticket is not assigned to you."
    if target["status"] != STATUS_IN_PROGRESS:
        return False, f"Ticket is not in progress (current status: {target['status']})."

    target["status"] = STATUS_RESOLVED
    target["resolved_at"] = datetime.now().isoformat(timespec="seconds")

    if target["category"] == "Password Reset":
        # description holds the service name the reset applies to (see module docstring)
        reset_vault_password(target["user_id"], target["description"])

    save_tickets(tickets)
    return True, f"Ticket {ticket_id[:8]} resolved."


# ---------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------
def get_analytics() -> dict:
    tickets = load_tickets()
    total = len(tickets)
    resolved = [t for t in tickets if t["status"] == STATUS_RESOLVED]
    open_count = total - len(resolved)

    # Average resolution time, in minutes, over tickets that have both
    # created_at and resolved_at timestamps we can parse.
    durations_seconds = []
    for t in resolved:
        try:
            created = datetime.fromisoformat(t["created_at"])
            done = datetime.fromisoformat(t["resolved_at"])
            durations_seconds.append((done - created).total_seconds())
        except (ValueError, TypeError, KeyError):
            continue  # skip malformed records rather than crashing

    avg_minutes = round((sum(durations_seconds) / len(durations_seconds)) / 60, 1) \
        if durations_seconds else 0.0

    by_category = {}
    for t in tickets:
        by_category[t["category"]] = by_category.get(t["category"], 0) + 1

    return {
        "total": total,
        "open": open_count,
        "resolved": len(resolved),
        "avg_resolution_minutes": avg_minutes,
        "by_category": by_category,
    }
