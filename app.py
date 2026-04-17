import streamlit as st
import mysql.connector
from datetime import datetime
import re
from sample import Ticket, build_update, build_lookup_maps, CONFIG

st.set_page_config(page_title="Ticket Update Tool", layout="centered")
st.title("🎫 Ticket Update Tool")

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

DT_FMT = "%Y-%m-%d %H:%M:%S"


def parse_dt(s: str) -> datetime:
    return datetime.strptime(s.strip(), DT_FMT)


def fmt_ticket_age(start_str: str, close_str: str) -> str:
    diff = parse_dt(close_str) - parse_dt(start_str)
    total = int(diff.total_seconds())
    if total <= 0:
        return "0 minutes"
    d = diff.days
    h = diff.seconds // 3600
    m = (diff.seconds % 3600) // 60
    parts = []
    if d: parts.append(f"{d} day{'s' if d != 1 else ''}")
    if h: parts.append(f"{h} hour{'s' if h != 1 else ''}")
    if m: parts.append(f"{m} minute{'s' if m != 1 else ''}")
    return " ".join(parts) if parts else "0 minutes"


def secs(start_str: str, end_str: str) -> int:
    return max(0, int((parse_dt(end_str) - parse_dt(start_str)).total_seconds()))


def validate_time(t: str) -> bool:
    return bool(re.match(r"^\d{2}:\d{2}:\d{2}$", t.strip()))


def format_dt(date, time: str) -> str:
    time = str(time).strip()
    if "." in time:
        time = time.split(".")[0]
    if not validate_time(time):
        raise ValueError(f"Invalid time format: '{time}' — expected HH:MM:SS")
    return f"{date.strftime('%Y-%m-%d')} {time}"


# ─────────────────────────────────────────────
#  DB HELPERS
# ─────────────────────────────────────────────

def get_connection():
    return mysql.connector.connect(**CONFIG)


def fetch_ticket_row(cursor, ref: str) -> dict | None:
    cursor.execute("""
        SELECT t.id, t.ref, t.start_date,
               i.ttr_started, i.ttr_finish_date, i.ttr_75_deadline
        FROM ticket t
        JOIN ticket_incident i ON t.id = i.id
        WHERE t.ref = %s
    """, (ref,))
    return cursor.fetchone()


def fetch_category_id(cursor, name: str) -> int | None:
    cursor.execute("""
        SELECT id FROM typology
        WHERE finalclass IN ('IncidentCategory','ServiceCategory','Category')
          AND name = %s LIMIT 1
    """, (name,))
    row = cursor.fetchone()
    return row["id"] if row else None


def fetch_subcategory_id(cursor, name: str) -> int | None:
    ALIASES = {
        "IT Issue \\ Application \\ Mobile Billing": "IT Issue \\ Application \\ Billing",
    }
    canonical = ALIASES.get(name, name)
    cursor.execute("""
        SELECT id FROM typology
        WHERE finalclass IN ('IncidentSubcategory','ServiceSubcategory','Subcategory')
          AND name = %s LIMIT 1
    """, (canonical,))
    row = cursor.fetchone()
    return row["id"] if row else None


# ─────────────────────────────────────────────
#  SQL BUILDERS
# ─────────────────────────────────────────────

def build_2input_sql(row: dict, resolution_time: str) -> str:
    start_str       = str(row["start_date"])
    ttr_started_str = str(row["ttr_started"] or start_str)
    ttr_finish_date = row["ttr_finish_date"]
    ttr_75_deadline = row["ttr_75_deadline"]

    ticket_age = fmt_ticket_age(start_str, resolution_time)
    timespent  = secs(ttr_started_str, resolution_time)

    # SLA 75%
    if ttr_75_deadline:
        dl75 = str(ttr_75_deadline)
        if parse_dt(dl75) <= parse_dt(resolution_time):
            overrun75 = secs(dl75, resolution_time)
            sla75 = f"i.ttr_75_passed=1, i.ttr_75_triggered=1, i.ttr_75_overrun={overrun75}, i.ttr_75_deadline='{dl75}'"
        else:
            sla75 = "i.ttr_75_passed=0, i.ttr_75_triggered=0, i.ttr_75_overrun=NULL, i.ttr_75_deadline=NULL"
    else:
        sla75 = "i.ttr_75_passed=0, i.ttr_75_triggered=0, i.ttr_75_overrun=NULL, i.ttr_75_deadline=NULL"

    # SLA 100%
    if ttr_finish_date:
        dl100 = str(ttr_finish_date)
        if parse_dt(dl100) < parse_dt(resolution_time):
            overrun100 = secs(dl100, resolution_time)
            sla100 = f"i.ttr_100_deadline='{dl100}', i.ttr_100_passed=1, i.ttr_100_triggered=1, i.ttr_100_overrun={overrun100}"
        else:
            sla100 = "i.ttr_100_deadline=NULL, i.ttr_100_passed=0, i.ttr_100_triggered=0, i.ttr_100_overrun=NULL"
    else:
        sla100 = "i.ttr_100_deadline=NULL, i.ttr_100_passed=0, i.ttr_100_triggered=0, i.ttr_100_overrun=NULL"

    return f"""UPDATE ticket t
JOIN ticket_incident i ON t.id = i.id
SET
    t.close_date      = '{resolution_time}',
    t.last_update     = '{resolution_time}',
    t.ticket_age      = '{ticket_age}',
    i.resolution_date = '{resolution_time}',
    i.ttr_stopped     = '{resolution_time}',
    i.tto_stopped     = '{resolution_time}',
    i.ttr_timespent   = {timespent},
    i.time_spent      = {timespent},
    {sla75},
    {sla100}
WHERE t.ref = '{row["ref"]}';"""


def build_4input_sql(row: dict, resolution_time: str, category_id, subcategory_id) -> str:
    base = build_2input_sql(row, resolution_time)
    extra_sets = []
    if category_id:
        extra_sets.append(f"i.category_id = {category_id}")
    if subcategory_id:
        extra_sets.append(f"i.subcategory_id = {subcategory_id}")
    if not extra_sets:
        return base
    # Insert extra SET clauses before the WHERE
    extra_sql = ",\n    ".join(extra_sets)
    return base.replace("WHERE t.ref", f",\n    {extra_sql}\nWHERE t.ref")


# ─────────────────────────────────────────────
#  MODE SELECTOR
# ─────────────────────────────────────────────

st.markdown("### ⚙️ Select Update Mode")

mode = st.radio(
    label="Update Mode",
    options=[
        "2-Input  (Ref + Resolution Time)",
        "4-Input  (Ref + Category + Subcategory + Resolution Time)"
    ],
    horizontal=True,
    label_visibility="collapsed"
)

is_4input = mode.startswith("4")

st.divider()

# ─────────────────────────────────────────────
#  FORM
# ─────────────────────────────────────────────

with st.form("ticket_form"):
    st.subheader("🎟️ Ticket Details")

    ref = st.text_input("Ticket Ref  (e.g. I-004176)", placeholder="I-004176")

    if is_4input:
        category    = st.text_input("Category",    placeholder="Applications")
        subcategory = st.text_input("Subcategory", placeholder="IT Issue \\ Application \\ Smart Meter")

    st.markdown("#### 🕒 Resolution Time")
    col1, col2 = st.columns(2)
    with col1:
        res_date = st.date_input("Resolution Date")
    with col2:
        res_time = st.text_input("Resolution Time (HH:MM:SS)", placeholder="10:40:48")

    submitted = st.form_submit_button("➕ Add to Queue")

# ─────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────

if "queue" not in st.session_state:
    st.session_state["queue"] = []       # list of dicts
if "sqls" not in st.session_state:
    st.session_state["sqls"] = []

# ─────────────────────────────────────────────
#  ADD TO QUEUE
# ─────────────────────────────────────────────

if submitted:
    try:
        resolution_dt = format_dt(res_date, res_time)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    if not ref.strip():
        st.error("❌ Ticket Ref is required.")
        st.stop()

    if any(item["ref"] == ref.strip() for item in st.session_state["queue"]):
        st.warning(f"⚠️ {ref} already in queue.")
    else:
        entry = {
            "ref": ref.strip(),
            "resolution_time": resolution_dt,
            "mode": "4input" if is_4input else "2input",
        }
        if is_4input:
            entry["category"]    = category.strip()
            entry["subcategory"] = subcategory.strip()

        st.session_state["queue"].append(entry)
        st.success(f"✅ {ref} added to queue.")

# ─────────────────────────────────────────────
#  SHOW QUEUE
# ─────────────────────────────────────────────

st.subheader("📋 Queue")

if not st.session_state["queue"]:
    st.info("No tickets in queue yet.")
else:
    for i, item in enumerate(st.session_state["queue"]):
        cols = st.columns([3, 4, 3, 1])
        cols[0].markdown(f"**{item['ref']}**")
        label = f"🕒 {item['resolution_time']}"
        if item["mode"] == "4input":
            label += f"  |  📁 {item.get('category','')} / {item.get('subcategory','')}"
        cols[1].caption(label)
        cols[2].caption(f"Mode: {'4-input' if item['mode']=='4input' else '2-input'}")
        if cols[3].button("🗑️", key=f"del_{i}"):
            st.session_state["queue"].pop(i)
            st.rerun()

    if st.button("🧹 Clear Queue"):
        st.session_state["queue"] = []
        st.session_state["sqls"]  = []
        st.rerun()

st.divider()

# ─────────────────────────────────────────────
#  GENERATE SQL
# ─────────────────────────────────────────────

if st.button("⚙️ Generate SQL Preview"):
    if not st.session_state["queue"]:
        st.warning("Queue is empty.")
        st.stop()

    sqls    = []
    errors  = []

    try:
        conn   = get_connection()
        cursor = conn.cursor(dictionary=True)

        for item in st.session_state["queue"]:
            row = fetch_ticket_row(cursor, item["ref"])
            if not row:
                errors.append(f"❌ {item['ref']} — not found in DB")
                continue

            if item["mode"] == "2input":
                sql = build_2input_sql(row, item["resolution_time"])

            else:
                cat_id = fetch_category_id(cursor, item["category"])
                sc_id  = fetch_subcategory_id(cursor, item["subcategory"])
                if not cat_id:
                    errors.append(f"⚠️ {item['ref']} — category '{item['category']}' not found (will skip)")
                if not sc_id:
                    errors.append(f"⚠️ {item['ref']} — subcategory '{item['subcategory']}' not found (will skip)")
                sql = build_4input_sql(row, item["resolution_time"], cat_id, sc_id)

            sqls.append((item["ref"], sql))

        cursor.close()
        conn.close()

    except mysql.connector.Error as e:
        st.error(f"DB error: {e}")
        st.stop()

    if errors:
        for err in errors:
            st.warning(err)

    st.session_state["sqls"] = sqls

    st.subheader("🧾 SQL Preview")
    for ref, sql in sqls:
        with st.expander(f"📄 {ref}"):
            st.code(sql, language="sql")

# ─────────────────────────────────────────────
#  EXECUTE
# ─────────────────────────────────────────────

if st.session_state.get("sqls"):
    st.divider()
    st.subheader("🚀 Execute Updates")
    st.warning(f"This will update **{len(st.session_state['sqls'])} ticket(s)** in the live database.")

    if st.button("✅ Confirm & Execute"):
        success, failed = 0, []

        try:
            conn   = get_connection()
            cursor = conn.cursor()

            for ref, sql in st.session_state["sqls"]:
                try:
                    cursor.execute(sql)
                    success += 1
                except mysql.connector.Error as e:
                    failed.append((ref, str(e)))

            conn.commit()
            cursor.close()
            conn.close()

        except mysql.connector.Error as e:
            st.error(f"Connection error: {e}")
            st.stop()

        if success:
            st.success(f"✅ {success}/{len(st.session_state['sqls'])} ticket(s) updated successfully.")

        if failed:
            st.error(f"❌ {len(failed)} failed:")
            for ref, err in failed:
                st.code(f"{ref}: {err}")

        # Clear after execution
        st.session_state["sqls"]  = []
        st.session_state["queue"] = []