import streamlit as st
import mysql.connector
import re
from datetime import datetime
from sample import Ticket, build_update, build_lookup_maps, CONFIG

st.set_page_config(page_title="Ticket Tool", layout="centered")

st.title("🎫 Ticket Update Tool")

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def validate_time(t):
    return re.match(r"^\d{2}:\d{2}:\d{2}$", t)

def format_dt(date, time):
    if not date or not time:
        return None

    time = str(time).strip()

    # remove milliseconds if pasted
    if "." in time:
        time = time.split(".")[0]

    if not validate_time(time):
        raise ValueError(f"Invalid time format: {time} (Expected HH:MM:SS)")

    return f"{date.strftime('%Y-%m-%d')} {time}"

def validate_required(ref, start_dt, ttr_dt):
    if not ref:
        return "Ref is required"
    if not start_dt:
        return "Start datetime required"
    if not ttr_dt:
        return "TTR finish datetime required"
    return None

# ─────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────

if "tickets" not in st.session_state:
    st.session_state["tickets"] = []

# ─────────────────────────────────────────────
# FORM
# ─────────────────────────────────────────────

with st.form("ticket_form"):

    st.subheader("Add Ticket")

    ref = st.text_input("Ref (Ticket ID)")

    subcategory = st.text_input("Subcategory")
    category = st.text_input("Category")

    status = st.selectbox("Status", ["closed", "assigned"])
    priority = st.selectbox("Priority", ["1", "2", "3", "4","5"])

    st.markdown("### 🕒 Date & Time")

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input("Start Date")
        start_time = st.text_input("Start Time (HH:MM:SS)", placeholder="11:26:11")

    with col2:
        close_date = st.date_input("Close Date")
        close_time = st.text_input("Close Time (HH:MM:SS)", placeholder="14:11:38")

    col3, col4 = st.columns(2)

    with col3:
        ttr_date = st.date_input("TTR Finish Date")

    with col4:
        ttr_time = st.text_input("TTR Finish Time (HH:MM:SS)", placeholder="23:26:11")

    division = st.text_input("Division Name")
    agent = st.text_input("Agent Name")

    ttr_100_passed = st.selectbox("SLA Breached?", [1, 0])

    submitted = st.form_submit_button("➕ Add Ticket")

# ─────────────────────────────────────────────
# ADD LOGIC
# ─────────────────────────────────────────────

if submitted:

    try:
        start_dt = format_dt(start_date, start_time)
        close_dt = format_dt(close_date, close_time)
        ttr_dt   = format_dt(ttr_date, ttr_time)

    except Exception as e:
        st.error(str(e))
        st.stop()

    error = validate_required(ref, start_dt, ttr_dt)

    if error:
        st.error(error)

    elif any(t[0] == ref for t in st.session_state["tickets"]):
        st.warning("⚠️ Ticket already added")

    else:
        ticket_tuple = (
            ref,
            subcategory,
            category,
            status,
            priority,
            start_dt,
            close_dt,
            ttr_dt,
            division,
            agent,
            ttr_100_passed
        )

        st.session_state["tickets"].append(ticket_tuple)
        st.success(f"✅ Added {ref}")

# ─────────────────────────────────────────────
# SHOW TICKETS
# ─────────────────────────────────────────────

st.subheader("📋 Current Tickets")

if not st.session_state["tickets"]:
    st.info("No tickets added yet")
else:
    for t in st.session_state["tickets"]:
        st.code(t)

# ─────────────────────────────────────────────
# GENERATE SQL
# ─────────────────────────────────────────────

if st.button("⚙️ Generate SQL"):

    if not st.session_state["tickets"]:
        st.warning("No tickets to process")
        st.stop()

    try:
        connection = mysql.connector.connect(**CONFIG)
        cursor = connection.cursor(dictionary=True)

        division_map, subcategory_map, category_map, agent_map = build_lookup_maps(cursor)

        sqls = []

        for r in st.session_state["tickets"]:

            ticket = Ticket(
                ref=r[0],
                subcategory=r[1],
                category=r[2],
                status=r[3],
                priority=r[4],
                start_date=r[5],
                close_date=r[6],
                ttr_finish_date=r[7],
                division_name=r[8],
                agent_name=r[9],
                ttr_100_passed=r[10]
            )

            warnings = []
            sql = build_update(ticket, division_map, subcategory_map, category_map, agent_map, warnings)

            sqls.append((ticket.ref, sql))

        st.session_state["sqls"] = sqls

        st.subheader("🧾 SQL Preview")

        for ref, sql in sqls:
            st.code(sql)

        cursor.close()
        connection.close()

    except Exception as e:
        st.error(str(e))

# ─────────────────────────────────────────────
# EXECUTE
# ─────────────────────────────────────────────

if "sqls" in st.session_state:

    if st.button("🚀 Execute Updates"):

        try:
            connection = mysql.connector.connect(**CONFIG)
            cursor = connection.cursor()

            for ref, sql in st.session_state["sqls"]:
                cursor.execute(sql)

            connection.commit()

            st.success("✅ All tickets updated successfully!")

            cursor.close()
            connection.close()

        except Exception as e:
            st.error(str(e))