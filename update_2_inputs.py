"""
update_2input.py
────────────────────────────────────────────────────────────
2-Input Ticket Updater
Inputs  : ref  (ticket reference, e.g. I-004325)
          close_date  (resolution datetime, e.g. 2026-03-10 14:11:38)

What it updates
  ticket          → close_date, last_update, ticket_age
  ticket_incident → resolution_date, ttr_stopped, tto_stopped,
                    ttr_timespent, time_spent,
                    ttr_75_*, ttr_100_*  (full SLA recalc)
────────────────────────────────────────────────────────────
"""

import sys
import mysql.connector
from datetime import datetime

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
CONFIG = {
    "host":     "10.10.10.92",
    "user":     "root",
    "password": "Usn7ets2020#",
    "database": "opfrasu_upclold",
}

DRY_RUN = False   # ← set True to preview SQL without committing

DT_FMT = "%Y-%m-%d %H:%M:%S"


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
#  FETCH CURRENT TICKET DATA FROM DB
# ─────────────────────────────────────────────

def fetch_ticket(cursor, ref: str) -> dict:
    cursor.execute("""
        SELECT
            t.id,
            t.ref,
            t.start_date,
            i.ttr_started,
            i.ttr_finish_date,
            i.ttr_75_deadline
        FROM ticket t
        JOIN ticket_incident i ON t.id = i.id
        WHERE t.ref = %s
    """, (ref,))
    row = cursor.fetchone()
    if not row:
        print(f"❌  Ticket '{ref}' not found in database.")
        sys.exit(1)
    return row


# ─────────────────────────────────────────────
#  BUILD SQL
# ─────────────────────────────────────────────

def build_sql(row: dict, close_date: str) -> str:
    start_str       = str(row["start_date"])           # from ticket.start_date
    ttr_started_str = str(row["ttr_started"] or start_str)
    ttr_finish_date = row["ttr_finish_date"]           # SLA-100 deadline
    ttr_75_deadline = row["ttr_75_deadline"]           # SLA-75 deadline

    ticket_age   = fmt_ticket_age(start_str, close_date)
    timespent    = secs(ttr_started_str, close_date)

    # ── SLA 75% ──────────────────────────────
    if ttr_75_deadline:
        dl75 = str(ttr_75_deadline)
        if parse_dt(dl75) <= parse_dt(close_date):
            overrun75 = secs(dl75, close_date)
            sla75 = (
                f"i.ttr_75_passed    = 1,\n"
                f"    i.ttr_75_triggered = 1,\n"
                f"    i.ttr_75_overrun   = {overrun75},\n"
                f"    i.ttr_75_deadline  = '{dl75}'"
            )
        else:
            sla75 = (
                "i.ttr_75_passed    = 0,\n"
                "    i.ttr_75_triggered = 0,\n"
                "    i.ttr_75_overrun   = NULL,\n"
                "    i.ttr_75_deadline  = NULL"
            )
    else:
        sla75 = (
            "i.ttr_75_passed    = 0,\n"
            "    i.ttr_75_triggered = 0,\n"
            "    i.ttr_75_overrun   = NULL,\n"
            "    i.ttr_75_deadline  = NULL"
        )

    # ── SLA 100% ─────────────────────────────
    if ttr_finish_date:
        dl100 = str(ttr_finish_date)
        if parse_dt(dl100) < parse_dt(close_date):
            overrun100 = secs(dl100, close_date)
            sla100 = (
                f"i.ttr_100_deadline  = '{dl100}',\n"
                f"    i.ttr_100_passed    = 1,\n"
                f"    i.ttr_100_triggered = 1,\n"
                f"    i.ttr_100_overrun   = {overrun100}"
            )
        else:
            sla100 = (
                "i.ttr_100_deadline  = NULL,\n"
                "    i.ttr_100_passed    = 0,\n"
                "    i.ttr_100_triggered = 0,\n"
                "    i.ttr_100_overrun   = NULL"
            )
    else:
        sla100 = (
            "i.ttr_100_deadline  = NULL,\n"
            "    i.ttr_100_passed    = 0,\n"
            "    i.ttr_100_triggered = 0,\n"
            "    i.ttr_100_overrun   = NULL"
        )

    sql = f"""
UPDATE ticket t
JOIN ticket_incident i ON t.id = i.id
SET
    -- ── ticket table ─────────────────────────────────
    t.close_date          = '{close_date}',
    t.last_update         = '{close_date}',
    t.ticket_age          = '{ticket_age}',

    -- ── ticket_incident table ────────────────────────
    i.resolution_date     = '{close_date}',
    i.ttr_stopped         = '{close_date}',
    i.tto_stopped         = '{close_date}',
    i.ttr_timespent       = {timespent},
    i.time_spent          = {timespent},

    -- ── SLA 75% ──────────────────────────────────────
    {sla75},

    -- ── SLA 100% ─────────────────────────────────────
    {sla100}

WHERE t.ref = '{row["ref"]}';
""".strip()

    return sql


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  2-Input Ticket Updater")
    print(f"  Mode: {'DRY RUN 🧪' if DRY_RUN else 'LIVE 🚨'}")
    print("=" * 55 + "\n")

    # ── Collect inputs ──────────────────────────────────
    ref        = input("Enter ticket ref (e.g. I-004325)            : ").strip()
    close_date = input("Enter resolution time      (YYYY-MM-DD HH:MM:SS): ").strip()

    # Validate date format
    try:
        parse_dt(close_date)
    except ValueError:
        print("❌  Invalid date format. Use YYYY-MM-DD HH:MM:SS")
        sys.exit(1)

    # ── Connect ─────────────────────────────────────────
    try:
        conn   = mysql.connector.connect(**CONFIG)
        cursor = conn.cursor(dictionary=True)
        print(f"\n🔌 Connected to `{CONFIG['database']}` on {CONFIG['host']}\n")
    except mysql.connector.Error as e:
        print(f"❌  Connection failed: {e}")
        sys.exit(1)

    # ── Fetch current ticket ─────────────────────────────
    row = fetch_ticket(cursor, ref)
    print(f"✅  Ticket found  → start_date : {row['start_date']}")
    print(f"                    ttr_finish  : {row['ttr_finish_date']}")
    print(f"                    ttr_75_dl   : {row['ttr_75_deadline']}\n")

    sql = build_sql(row, close_date)

    # ── Preview ──────────────────────────────────────────
    print("📋  Generated SQL:\n")
    print(sql)
    print()

    if DRY_RUN:
        print("✅  DRY RUN — nothing committed. Set DRY_RUN=False to execute.\n")
        cursor.close(); conn.close()
        return

    # ── Execute ──────────────────────────────────────────
    confirm = input(f"⚠️  Apply this UPDATE to LIVE DB? Type YES to continue: ").strip()
    if confirm != "YES":
        print("❌  Aborted.")
        cursor.close(); conn.close()
        return

    try:
        cursor.execute(sql)
        conn.commit()
        print(f"\n✅  Ticket {ref} updated successfully.")
    except mysql.connector.Error as e:
        print(f"❌  Update failed: {e}")
        conn.rollback()

    cursor.close()
    conn.close()
    print("🔌  Connection closed.")


if __name__ == "__main__":
    main()