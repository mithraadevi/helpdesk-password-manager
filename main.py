"""
main.py
-------
Streamlit entry point. Handles:
  - the login screen (role selection: User / Staff, plus registration)
  - routing to the User dashboard or Staff dashboard based on session state

Run with:  streamlit run main.py

All actual business logic lives in auth.py / tickets.py / vault.py --
this file is deliberately just UI + wiring, so it's easy to explain each
piece in isolation during a viva.
"""

import streamlit as st
import pandas as pd

import auth
import tickets
import vault

st.set_page_config(page_title="Help Desk + Password Manager", page_icon="🎫", layout="wide")

# -----------------------------------------------------------------------
# Session state = "who is logged in right now, in this browser tab".
# Streamlit re-runs this whole script top-to-bottom on every interaction,
# so anything that must survive between reruns (like "am I logged in?")
# has to live in st.session_state instead of a plain variable.
# -----------------------------------------------------------------------
if "role" not in st.session_state:
    st.session_state.role = None    # None | "user" | "staff"
    st.session_state.id = None      # user_id or staff_id
    st.session_state.name = None    # display name


def logout():
    st.session_state.role = None
    st.session_state.id = None
    st.session_state.name = None


# =========================================================================
# LOGIN SCREEN
# =========================================================================
def login_screen():
    st.title("🎫 Help Desk + Password Manager")
    st.caption("Select your role, then log in (or register if you're new).")

    role_choice = st.radio("I am a:", ["User", "Staff"], horizontal=True)

    if role_choice == "User":
        tab_login, tab_register = st.tabs(["Login", "Register"])

        with tab_login:
            with st.form("user_login_form"):
                user_id = st.text_input("User ID")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")
            if submitted:
                ok, result = auth.login_user(user_id.strip(), password)
                if ok:
                    st.session_state.role = "user"
                    st.session_state.id = user_id.strip()
                    st.session_state.name = result
                    st.rerun()
                else:
                    st.error(result)  # "User ID not found." / "Incorrect password."

        with tab_register:
            st.caption("New here? Create an account to get a User ID.")
            with st.form("user_register_form"):
                name = st.text_input("Your name")
                password = st.text_input("Choose a password", type="password")
                submitted = st.form_submit_button("Register")
            if submitted:
                if not name.strip() or not password:
                    st.error("Name and password are both required.")
                else:
                    new_id = auth.register_user(name.strip(), password)
                    st.success(f"Account created! Your **User ID** is `{new_id}` "
                               f"— save it, you'll need it to log in.")

    else:  # Staff
        tab_login, tab_register = st.tabs(["Login", "Register"])

        with tab_login:
            st.caption("Staff login is ID-only, per the internal-trust model of this system.")
            with st.form("staff_login_form"):
                staff_id = st.text_input("Staff ID")
                submitted = st.form_submit_button("Login")
            if submitted:
                ok, result = auth.login_staff(staff_id.strip())
                if ok:
                    st.session_state.role = "staff"
                    st.session_state.id = staff_id.strip()
                    st.session_state.name = result
                    st.rerun()
                else:
                    st.error(result)

        with tab_register:
            with st.form("staff_register_form"):
                name = st.text_input("Staff name")
                submitted = st.form_submit_button("Register as Staff")
            if submitted:
                if not name.strip():
                    st.error("Name is required.")
                else:
                    new_id = auth.register_staff(name.strip())
                    st.success(f"Staff account created! Your **Staff ID** is `{new_id}`.")


# =========================================================================
# USER DASHBOARD
# =========================================================================
def user_dashboard():
    st.sidebar.title(f"👤 {st.session_state.name}")
    st.sidebar.caption(f"User ID: `{st.session_state.id}`")
    page = st.sidebar.radio("Menu", ["Submit a Ticket", "View My Tickets", "Manage My Vault"])
    st.sidebar.button("Logout", on_click=logout)

    user_id = st.session_state.id

    # --------------------------------------------------------------
    if page == "Submit a Ticket":
        st.header("📝 Submit a Ticket")

        category = st.selectbox("Category", tickets.CATEGORIES)

        if category == "Password Reset":
            description = st.text_input(
                "Which service is this password reset for?",
                placeholder="e.g. Gmail",
                help="Enter the exact service name as saved in your vault. "
                     "This is how staff know which vault entry to reset.",
            )
        else:
            description = st.text_area("Describe your issue")

        if st.button("Submit Ticket"):
            if not description.strip():
                st.error("Please provide a description before submitting.")
            else:
                t = tickets.create_ticket(user_id, category, description.strip())
                st.success(f"Ticket submitted! Ticket ID: `{t['ticket_id'][:8]}`")

    # --------------------------------------------------------------
    elif page == "View My Tickets":
        st.header("📋 My Tickets")
        my_tickets = tickets.get_user_tickets(user_id)

        if not my_tickets:
            st.info("You haven't submitted any tickets yet.")
        else:
            rows = [{
                "Ticket ID": t["ticket_id"][:8],
                "Category": t["category"],
                "Description": t["description"],
                "Status": t["status"],
                "Created": t["created_at"],
                "Resolved": t["resolved_at"] or "—",
            } for t in sorted(my_tickets, key=lambda x: x["created_at"], reverse=True)]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # --------------------------------------------------------------
    elif page == "Manage My Vault":
        st.header("🔐 Manage My Vault")

        st.subheader("Add a New Vault Entry")
        with st.form("add_vault_form"):
            service = st.text_input("Service name", placeholder="e.g. Gmail")
            auto_gen = st.checkbox("Auto-generate a strong password", value=True)
            manual_pw = "" if auto_gen else st.text_input("Password", type="password")
            submitted = st.form_submit_button("Save Entry")

        if submitted:
            if not service.strip():
                st.error("Service name is required.")
            else:
                plain = vault.generate_strong_password() if auto_gen else manual_pw
                if not plain:
                    st.error("Enter a password, or check 'Auto-generate'.")
                else:
                    ok, msg = vault.add_vault_entry(user_id, service.strip(), plain)
                    if ok:
                        st.success(msg)
                        if auto_gen:
                            st.info(f"Your generated password (shown once — save it now): `{plain}`")
                    else:
                        st.error(msg)

        st.divider()
        st.subheader("Your Saved Services")
        st.caption("Decrypted passwords are never shown here — only service names and status.")

        entries = vault.get_user_entries(user_id)
        if not entries:
            st.info("No vault entries yet.")
        else:
            for e in entries:
                c1, c2, c3, c4 = st.columns([3, 3, 2, 2])
                c1.write(f"**{e['service_name']}**")
                c2.write(f"Last updated: {e['last_updated'] or '—'}")
                if e.get("reset_pending"):
                    c3.warning("Reset ready")
                    if c4.button("Claim", key=f"claim_{e['service_name']}"):
                        new_pw = vault.claim_reset(user_id, e["service_name"])
                        if new_pw:
                            st.success(f"New password for **{e['service_name']}**: `{new_pw}`")
                            st.caption("This is shown once. Save it now.")
                        else:
                            st.error("Nothing to claim.")
                else:
                    c3.write("Up to date")


# =========================================================================
# STAFF DASHBOARD
# =========================================================================
def staff_dashboard():
    st.sidebar.title(f"🧑‍💼 {st.session_state.name}")
    st.sidebar.caption(f"Staff ID: `{st.session_state.id}`")

    # Availability toggle -- lets you demo auto-assignment realistically
    # (e.g. mark yourself unavailable and watch auto-assign report nobody's free).
    staff_all = auth.load_staff()
    my_record = staff_all.get(st.session_state.id, {})
    is_available = st.sidebar.checkbox("Available for assignment", value=my_record.get("available", True))
    if is_available != my_record.get("available"):
        staff_all[st.session_state.id]["available"] = is_available
        auth.save_staff(staff_all)
        st.sidebar.success("Availability updated.")

    page = st.sidebar.radio("Menu", ["Run Auto-Assignment", "Resolve a Ticket", "View Analytics"])
    st.sidebar.button("Logout", on_click=logout)

    # --------------------------------------------------------------
    if page == "Run Auto-Assignment":
        st.header("⚙️ Run Auto-Assignment")
        st.write("Assigns the **oldest** unassigned ticket (FIFO) to the "
                 "**first available** staff member.")

        if st.button("Run Assignment"):
            staff_all = auth.load_staff()
            ok, msg = tickets.auto_assign(staff_all, auth.save_staff)
            (st.success if ok else st.warning)(msg)

        st.divider()
        st.subheader("Open Tickets Queue")
        open_tickets = [t for t in tickets.load_tickets() if t["status"] == tickets.STATUS_OPEN]
        if open_tickets:
            rows = [{
                "Ticket ID": t["ticket_id"][:8],
                "Category": t["category"],
                "Created": t["created_at"],
            } for t in sorted(open_tickets, key=lambda x: x["created_at"])]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No open tickets waiting.")

    # --------------------------------------------------------------
    elif page == "Resolve a Ticket":
        st.header("✅ Resolve a Ticket")
        my_assigned = tickets.get_tickets_assigned_to(st.session_state.id)

        if not my_assigned:
            st.info("No tickets are currently assigned to you.")
        else:
            options = {
                f"{t['ticket_id'][:8]} — {t['category']} — {t['description'][:40]}": t["ticket_id"]
                for t in my_assigned
            }
            choice = st.selectbox("Select a ticket to resolve", list(options.keys()))
            if st.button("Mark as Resolved"):
                ok, msg = tickets.resolve_ticket(options[choice], st.session_state.id)
                if ok:
                    st.success(msg)
                    st.caption("If this was a Password Reset ticket, a new password was "
                               "generated and encrypted into the user's vault automatically. "
                               "Staff never see the plaintext.")
                else:
                    st.error(msg)

    # --------------------------------------------------------------
    elif page == "View Analytics":
        st.header("📊 Analytics")
        stats = tickets.get_analytics()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Tickets", stats["total"])
        c2.metric("Open / In Progress", stats["open"])
        c3.metric("Resolved", stats["resolved"])
        c4.metric("Avg Resolution (min)", stats["avg_resolution_minutes"])

        st.subheader("Tickets by Category")
        if stats["by_category"]:
            st.bar_chart(pd.DataFrame.from_dict(stats["by_category"], orient="index", columns=["Count"]))
        else:
            st.info("No ticket data yet.")


# =========================================================================
# ROUTER
# =========================================================================
if st.session_state.role is None:
    login_screen()
elif st.session_state.role == "user":
    user_dashboard()
elif st.session_state.role == "staff":
    staff_dashboard()
