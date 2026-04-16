import mysql.connector
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import sys

@dataclass
class Ticket:
    ref: str
    subcategory: str       # e.g. "IT Issue \\ Application \\ Database"
    category: str          # e.g. "Applications"
    status: str            # e.g. "closed"
    priority: str          # e.g. "4"
    start_date: str
    close_date: Optional[str]
    ttr_finish_date: str
    division_name: str
    agent_name: str        # username or full name as in DB
    ttr_100_passed: int    # 1 = yes


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
CONFIG = {
    "host":     "10.10.10.sample",
    "user":     "sample",
    "password": "sample",
    "database": "sample",
}

DRY_RUN = False   # ← Set False to commit live changes

# ─────────────────────────────────────────────
#  TICKET DATA  (extracted from PDF)
#  Fields: ref, subcategory, category, status, priority,
#          start_date, close_date, ttr_finish_date,
#          division_name, agent_name, ttr_100_passed
# ─────────────────────────────────────────────

RAW_TICKETS = [
    ('I-004325', 'IT Issue \\ Application \\ Billing', 'Applications', 'closed', '4', '2026-03-10 13:50:37', '2026-03-10 14:11:38', '2026-03-09 23:26:11', 'Data_Center', 'ankitp', 1)
]

TICKETS = [
    Ticket(ref=r[0], subcategory=r[1], category=r[2], status=r[3], priority=r[4],
           start_date=r[5], close_date=r[6], ttr_finish_date=r[7],
           division_name=r[8], agent_name=r[9], ttr_100_passed=r[10])
    for r in RAW_TICKETS
]


# ─────────────────────────────────────────────
#  DATE / TIME HELPERS
# ─────────────────────────────────────────────

DT_FMT = "%Y-%m-%d %H:%M:%S"


def parse_dt(s: str) -> datetime:
    return datetime.strptime(s, DT_FMT)


def format_ticket_age(start_str: str, close_str: Optional[str]) -> Optional[str]:
    """
    Returns human-readable age like '2 days 6 hours 6 minutes'.
    Returns None if close_date is missing or close is before start.
    """
    if not close_str:
        return None
    diff = parse_dt(close_str) - parse_dt(start_str)
    total_secs = int(diff.total_seconds())
    if total_secs < 0:
        return None
    days    = diff.days
    hours   = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    parts = []
    if days:    parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:   parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes: parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return " ".join(parts) if parts else "0 minutes"


def seconds_between(start_str: str, end_str: str) -> int:
    """Returns elapsed seconds (non-negative) between two datetime strings."""
    return max(0, int((parse_dt(end_str) - parse_dt(start_str)).total_seconds()))


# ─────────────────────────────────────────────
#  ID LOOKUP  (batch, single round-trip each)
# ─────────────────────────────────────────────

def build_lookup_maps(cursor):
    """Fetch all needed IDs in a few bulk queries and return lookup dicts."""

    # 1. Divisions
    cursor.execute(
        "SELECT id, name FROM typology WHERE finalclass = 'Division'"
    )
    division_map = {row["name"]: row["id"] for row in cursor.fetchall()}

    # 2. Subcategories
    cursor.execute(
        "SELECT id, name FROM typology WHERE finalclass IN ('IncidentSubcategory','ServiceSubcategory','Subcategory')"
    )
    subcategory_map = {row["name"]: row["id"] for row in cursor.fetchall()}

    # 3. Categories
    cursor.execute(
        "SELECT id, name FROM typology WHERE finalclass IN ('IncidentCategory','ServiceCategory','Category')"
    )
    category_map = {row["name"]: row["id"] for row in cursor.fetchall()}

    # 4. Agents — match on login (first_name in person table OR contactname in contact)
    cursor.execute("""
        SELECT p.id, p.first_name, CONCAT(p.first_name,' ', COALESCE(co.name,'')) AS full_name
        FROM person p
        LEFT JOIN contact co ON co.id = p.id
    """)
    agent_rows = cursor.fetchall()
    agent_map = {}
    for row in agent_rows:
        login = (row["first_name"] or "").strip()
        full  = (row["full_name"] or "").strip()
        if login:
            agent_map[login] = row["id"]
        if full and full != login:
            agent_map[full] = row["id"]
        if full:
            agent_map[f"- {full}"] = row["id"]

    # ── Subcategory aliases ──
    for alias, canonical in [
        ("IT Issue \\ Application \\ Mobile Billing", "IT Issue \\ Application \\ Billing"),
    ]:
        if alias not in subcategory_map and canonical in subcategory_map:
            subcategory_map[alias] = subcategory_map[canonical]

    return division_map, subcategory_map, category_map, agent_map


def resolve(val, lookup, label, ref, warnings):
    if val is None:
        return None
    result = lookup.get(val)
    if result is None:
        warnings.append(f"  ⚠️  [{ref}] {label} not found: '{val}'")
    return result


# ─────────────────────────────────────────────
#  STATUS MAP
# ─────────────────────────────────────────────
STATUS_MAP = {
    "closed":        ("closed",   "closed"),
    "assigned":      ("assigned", "assigned"),
    "escalated ttr": ("assigned", "assigned"),
}


# ─────────────────────────────────────────────
#  BUILD SQL
# ─────────────────────────────────────────────
def build_update(t: Ticket, division_map, subcategory_map, category_map, agent_map, warnings):
    op_status, inc_status = STATUS_MAP.get(t.status.lower(), ("closed", "closed"))

    div_id   = resolve(t.division_name,  division_map,    "Division",    t.ref, warnings)
    sc_id    = resolve(t.subcategory,    subcategory_map, "Subcategory", t.ref, warnings)
    cat_id   = resolve(t.category,       category_map,    "Category",    t.ref, warnings)
    agent_id = resolve(t.agent_name,     agent_map,       "Agent",       t.ref, warnings)

    # ── Computed values ──────────────────────────────────────
    ticket_age    = format_ticket_age(t.start_date, t.close_date)
    ttr_timespent = seconds_between(t.start_date, t.close_date) if t.close_date else 0

    # ── Conditional clauses ─────────────────────────────────
    close_clause       = f"'{t.close_date}'" if t.close_date else "NULL"
    last_update_clause = close_clause
    ticket_age_clause  = f"'{ticket_age}'" if ticket_age else "NULL"
    resolution_clause  = close_clause

    # ── Build SET clauses safely ─────────────────────────────
    set_clauses = []

    # ticket table
    set_clauses.append(f"t.operational_status = '{op_status}'")
    set_clauses.append(f"t.ticket_type = 'IT Issue'")
    set_clauses.append(f"t.start_date = '{t.start_date}'")
    set_clauses.append(f"t.close_date = {close_clause}")
    set_clauses.append(f"t.last_update = {last_update_clause}")
    set_clauses.append(f"t.ticket_age = {ticket_age_clause}")

    if agent_id:
        set_clauses.append(f"t.agent_id = {agent_id}")

    # ticket_incident table
    set_clauses.append(f"i.status = '{inc_status}'")
    set_clauses.append(f"i.priority = '{t.priority}'")
    set_clauses.append(f"i.ttr_finish_date = '{t.ttr_finish_date}'")
    set_clauses.append(f"i.resolution_date = {resolution_clause}")
    set_clauses.append(f"i.ttr_stopped = {resolution_clause}")
    set_clauses.append(f"i.ttr_timespent = {ttr_timespent}")
    set_clauses.append(f"i.time_spent = {ttr_timespent}")

    # ── TTR lifecycle 
    set_clauses.append(f"i.ttr_started = '{t.start_date}'")
    set_clauses.append(f"i.ttr_laststart = '{t.start_date}'")

    # ── TTO lifecycle 
    set_clauses.append(f"i.tto_started = '{t.start_date}'")
    set_clauses.append(f"i.tto_laststart = '{t.start_date}'")
    set_clauses.append(f"i.tto_stopped = {resolution_clause}")
    set_clauses.append(f"i.tto_timespent = {ttr_timespent}")
    set_clauses.append(f"i.assignment_date = '{t.start_date}'")
    set_clauses.append(f"i.ttr_100_passed = {t.ttr_100_passed}")

    if cat_id:
        set_clauses.append(f"i.category_id = {cat_id}")
    if sc_id:
        set_clauses.append(f"i.subcategory_id = {sc_id}")
    if div_id:
        set_clauses.append(f"i.division_id = {div_id}")

    # ── SLA 75% ─────────────────────────────────────────────
    if t.close_date:
        set_clauses.append(
            f"i.ttr_75_passed = IF(i.ttr_75_deadline IS NOT NULL AND i.ttr_75_deadline <= '{t.close_date}', 1, 0)"
        )
        set_clauses.append(
            f"i.ttr_75_triggered = IF(i.ttr_75_deadline IS NOT NULL AND i.ttr_75_deadline <= '{t.close_date}', 1, 0)"
        )
        set_clauses.append(
            f"""i.ttr_75_overrun = IF(i.ttr_75_deadline IS NOT NULL AND i.ttr_75_deadline <= '{t.close_date}',
            TIMESTAMPDIFF(SECOND, i.ttr_75_deadline, '{t.close_date}'), NULL)"""
        )
        set_clauses.append(
            f"""i.ttr_75_deadline = IF(i.ttr_75_deadline IS NOT NULL AND i.ttr_75_deadline <= '{t.close_date}',
            i.ttr_75_deadline, NULL)"""
        )
    else:
        set_clauses.append("i.ttr_75_passed = 0")
        set_clauses.append("i.ttr_75_triggered = 0")
        set_clauses.append("i.ttr_75_overrun = NULL")
        set_clauses.append("i.ttr_75_deadline = NULL")

    # ── SLA 100% ────────────────────────────────────────────
    if t.close_date and t.ttr_finish_date:
        close_dt  = parse_dt(t.close_date)
        finish_dt = parse_dt(t.ttr_finish_date)

        if close_dt > finish_dt:
            overrun_100 = seconds_between(t.ttr_finish_date, t.close_date)
            set_clauses.append(f"i.ttr_100_deadline = '{t.ttr_finish_date}'")
            set_clauses.append("i.ttr_100_passed = 1")
            set_clauses.append("i.ttr_100_triggered = 1")
            set_clauses.append(f"i.ttr_100_overrun = {overrun_100}")
        else:
            set_clauses.append("i.ttr_100_deadline = NULL")
            set_clauses.append("i.ttr_100_passed = 0")
            set_clauses.append("i.ttr_100_triggered = 0")
            set_clauses.append("i.ttr_100_overrun = NULL")

    # ── Final SQL ───────────────────────────────────────────
    set_sql = ",\n    ".join(set_clauses)

    sql = f"""
UPDATE ticket t
JOIN ticket_incident i ON t.id = i.id
SET
    {set_sql}
WHERE t.ref = '{t.ref}';
""".strip()

    return sql

# ─────────────────────────────────────────────
#  AUTO-UPDATE TRIGGER  (print-only, run once)
# ─────────────────────────────────────────────

TRIGGER_SQL = """\
-- ══════════════════════════════════════════════════════════════════════
--  AUTO-UPDATE TRIGGER
--  Drop + recreate so we can safely re-run.
--  After any UPDATE that changes resolution_date on ticket_incident,
--  all dependent TTR / SLA fields recalculate automatically.
-- ══════════════════════════════════════════════════════════════════════

DROP TRIGGER IF EXISTS trg_ticket_incident_resolution_update;

DELIMITER $$

CREATE TRIGGER trg_ticket_incident_resolution_update
AFTER UPDATE ON ticket_incident
FOR EACH ROW
BEGIN
    -- Only fire when resolution_date actually changes
    IF NOT (NEW.resolution_date <=> OLD.resolution_date) THEN

        -- ── ticket table ─────────────────────────────────────────────
        UPDATE ticket t
        SET
            t.close_date  = NEW.resolution_date,
            t.last_update = NEW.resolution_date,
            t.ticket_age  = (
                SELECT
                    CONCAT(
                        CASE WHEN DATEDIFF(NEW.resolution_date, t2.start_date) > 0
                             THEN CONCAT(DATEDIFF(NEW.resolution_date, t2.start_date), ' days ') ELSE '' END,
                        CASE WHEN FLOOR(TIME_TO_SEC(TIMEDIFF(NEW.resolution_date, t2.start_date)) % 86400 / 3600) > 0
                             THEN CONCAT(FLOOR(TIME_TO_SEC(TIMEDIFF(NEW.resolution_date, t2.start_date)) % 86400 / 3600), ' hours ') ELSE '' END,
                        CASE WHEN FLOOR(TIME_TO_SEC(TIMEDIFF(NEW.resolution_date, t2.start_date)) % 3600 / 60) > 0
                             THEN CONCAT(FLOOR(TIME_TO_SEC(TIMEDIFF(NEW.resolution_date, t2.start_date)) % 3600 / 60), ' minutes') ELSE '0 minutes' END
                    )
                FROM ticket t2 WHERE t2.id = NEW.id
            )
        WHERE t.id = NEW.id;

        -- ── ticket_incident: ttr_stopped, timespent ──────────────────
        SET NEW.ttr_stopped    = NEW.resolution_date;
        SET NEW.ttr_timespent  = TIMESTAMPDIFF(SECOND, NEW.tto_started, NEW.resolution_date);
        SET NEW.time_spent     = NEW.ttr_timespent;

        -- ── SLA 75% ───────────────────────────────────────────────────
        IF NEW.ttr_75_deadline IS NOT NULL AND NEW.ttr_75_deadline <= NEW.resolution_date THEN
            -- Deadline was MISSED
            SET NEW.ttr_75_passed    = 1;
            SET NEW.ttr_75_triggered = 1;
            SET NEW.ttr_75_overrun   = TIMESTAMPDIFF(SECOND, NEW.ttr_75_deadline, NEW.resolution_date);
        ELSE
            -- Deadline met OR no deadline set
            SET NEW.ttr_75_passed    = 0;
            SET NEW.ttr_75_triggered = 0;
            SET NEW.ttr_75_overrun   = NULL;
            SET NEW.ttr_75_deadline  = NULL;
        END IF;

        -- ── SLA 100% ──────────────────────────────────────────────────
        IF NEW.ttr_finish_date IS NOT NULL AND NEW.ttr_finish_date < NEW.resolution_date THEN
            SET NEW.ttr_100_deadline  = NEW.ttr_finish_date;
            SET NEW.ttr_100_passed    = 1;
            SET NEW.ttr_100_triggered = 1;
            SET NEW.ttr_100_overrun   = TIMESTAMPDIFF(SECOND, NEW.ttr_finish_date, NEW.resolution_date);
        ELSE
            SET NEW.ttr_100_deadline  = NULL;
            SET NEW.ttr_100_passed    = 0;
            SET NEW.ttr_100_triggered = 0;
            SET NEW.ttr_100_overrun   = NULL;
        END IF;

    END IF;
END$$

DELIMITER ;
-- ══════════════════════════════════════════════════════════════════════
"""


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"  Bulk Ticket Migration — {len(TICKETS)} tickets")
    print(f"  Mode: {'DRY RUN 🧪' if DRY_RUN else 'LIVE 🚨'}")
    print("=" * 60 + "\n")

    try:
        connection = mysql.connector.connect(**CONFIG)
        cursor = connection.cursor(dictionary=True)
        print(f"🔌 Connected to `{CONFIG['database']}` on {CONFIG['host']}\n")
    except mysql.connector.Error as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    print("🔍 Building lookup maps from DB...")
    division_map, subcategory_map, category_map, agent_map = build_lookup_maps(cursor)
    print(f"   Divisions:    {len(division_map)}")
    print(f"   Subcategories:{len(subcategory_map)}")
    print(f"   Categories:   {len(category_map)}")
    print(f"   Agents:       {len(agent_map)}\n")

    warnings = []
    sqls = []

    for t in TICKETS:
        sql = build_update(t, division_map, subcategory_map, category_map, agent_map, warnings)
        sqls.append((t.ref, sql))

    # ── Show warnings ───────────────────────────────────────
    if warnings:
        print("⚠️  WARNINGS (unresolved lookups):")
        for w in warnings:
            print(w)
        print()

    # ── DRY RUN MODE ───────────────────────────────────────
    if DRY_RUN:
        print("📋 Preview — generated SQL:\n")
        for ref, sql in sqls:
            print(f"-- {ref}")
            print(sql)
            print()

        print(f"✅ DRY RUN complete. {len(sqls)} statements generated, nothing committed.\n")
        print("👉 Set DRY_RUN = False to execute.\n")

    # ── LIVE MODE ──────────────────────────────────────────
    else:
        confirm = input(f"⚠️  About to UPDATE {len(sqls)} tickets in LIVE DB. Type YES to continue: ")

        if confirm.strip() != "YES":
            print("❌ Aborted by user.")
            cursor.close()
            connection.close()
            return

        success, failed = 0, []

        for ref, sql in sqls:
            try:
                cursor.execute(sql)
                success += 1
            except mysql.connector.Error as e:
                failed.append((ref, str(e)))
                print(f"❌ {ref}: {e}")

        try:
            connection.commit()
        except mysql.connector.Error as e:
            print(f"❌ Commit failed: {e}")
            connection.rollback()
            cursor.close()
            connection.close()
            return

        print(f"\n✅ Done. {success}/{len(sqls)} tickets updated.")

        if failed:
            print(f"\n❌ {len(failed)} failed:")
            for ref, err in failed:
                print(f"   {ref}: {err}")

    cursor.close()
    connection.close()
    print("\n🔌 Connection closed.")

if __name__ == "__main__":
    main()
