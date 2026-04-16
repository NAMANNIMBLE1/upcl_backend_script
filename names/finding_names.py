import mysql.connector

CONFIG = {
    "host":     "10.10.10.92",
    "user":     "root",
    "password": "Usn7ets2020#",
    "database": "opfrasu_upclold",
}

conn = mysql.connector.connect(**CONFIG)
cursor = conn.cursor(dictionary=True)

# ── EDIT THESE ──────────────────────────────────────────
SEARCH_AGENT    = "deepika"        # partial first_name
SEARCH_DIVISION = "DOIWALA"         # partial division name
SEARCH_CATEGORY = "applications"   # partial category name
SEARCH_SUBCAT   = "database"       # partial subcategory name
# ────────────────────────────────────────────────────────

print("👤 AGENTS:")
cursor.execute("""
    SELECT p.id, p.first_name, co.name AS last_name
    FROM person p
    JOIN contact co ON co.id = p.id
    WHERE p.first_name LIKE %s
    ORDER BY p.first_name
""", (f"%{SEARCH_AGENT}%",))
for r in cursor.fetchall():
    print(f"   id={r['id']:4d}  {r['first_name']} {r['last_name']}")

print("\n🏢 DIVISIONS:")
cursor.execute("""
    SELECT id, name FROM typology
    WHERE finalclass = 'Division' AND name LIKE %s
    ORDER BY name
""", (f"%{SEARCH_DIVISION}%",))
for r in cursor.fetchall():
    print(f"   id={r['id']:4d}  {r['name']}")

print("\n📁 CATEGORIES:")
cursor.execute("""
    SELECT id, name FROM typology
    WHERE finalclass = 'Category' AND name LIKE %s
    ORDER BY name
""", (f"%{SEARCH_CATEGORY}%",))
for r in cursor.fetchall():
    print(f"   id={r['id']:4d}  {r['name']}")

print("\n📂 SUBCATEGORIES:")
cursor.execute("""
    SELECT id, name FROM typology
    WHERE finalclass = 'Subcategory' AND name LIKE %s
    ORDER BY name
""", (f"%{SEARCH_SUBCAT}%",))
for r in cursor.fetchall():
    print(f"   id={r['id']:4d}  {r['name']}")

cursor.close()
conn.close()
