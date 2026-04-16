# 🎫 UPCL Ticket Update Tool

A Python-based tool to update ticket data in the UPCL system.

Supports:
- Script-based bulk updates
- Streamlit frontend (easy UI)
- SLA (TTR/TTO) recalculation
- SQL preview before execution

---

# 📦 Installation

## 1. Clone Repository

git clone https://github.com/NAMANNIMBLE1/upcl_backend_script.git  
cd upcl_backend_script  

---

## 2. Setup Python Environment

python -m venv .venv  

### Activate Environment

Windows:
.venv\Scripts\activate  

Linux / Mac:
source .venv/bin/activate  

---

## 3. Install Dependencies

pip install -r requirements.txt  

---

# 🖥️ Running the Project

## ▶️ Frontend (Recommended)

streamlit run app.py  

👉 Opens UI in browser where you can:
- Add tickets
- Generate SQL
- Execute updates

---

## ⚙️ Script Mode

python sample.py  

---

# 🧠 Usage

## 🔹 1. Configure Database

Edit inside `sample.py`:

CONFIG = {
    "host": "your_host",
    "user": "your_user",
    "password": "your_password",
    "database": "your_database"
}

---

## 🔹 2. Dry Run Mode (Script Only)

Set:

DRY_RUN = True  

| Mode | Behavior |
|------|--------|
| True | Shows SQL only |
| False | Executes updates |

---

## 🔹 3. Add Ticket Data (Script Mode)

Edit:

RAW_TICKETS = []

### Format:

(
  ref,
  subcategory,
  category,
  status,
  priority,
  start_date,
  close_date,
  ttr_finish_date,
  division_name,
  agent_name,
  ttr_100_passed
)

---

## ✅ Example

RAW_TICKETS = [
    (
        'I-004325',
        'IT Issue \\ Application \\ Billing',
        'Applications',
        'closed',
        '4',
        '2026-03-10 13:50:37',
        '2026-03-10 14:11:38',
        '2026-03-09 23:26:11',
        'Data_Center',
        'ankitp',
        1
    )
]

---

# 🧾 Field Explanation

ref → Ticket ID  
subcategory → Full path  
category → Main category  
status → closed / assigned  
priority → 1 to 5 (1 = Critical, 5 = Low)  
start_date → Start datetime  
close_date → Resolution datetime  
ttr_finish_date → SLA deadline  
division_name → Division  
agent_name → Assigned agent  
ttr_100_passed → 1 = SLA breached  

---

# 🖥️ Frontend Usage

Run:

streamlit run app.py  

Steps:

1. Enter ticket details  
2. Click ➕ Add Ticket  
3. Click ⚙️ Generate SQL  
4. Review output  
5. Click 🚀 Execute Updates  

⚠️ Note: Frontend directly updates DB (no dry run)

---

# ⚠️ Important Notes

- Always verify data before execution  
- Changes are permanent  
- Ensure correct:
  - Agent name
  - Division name
  - Category mapping  
- Time format must be:

HH:MM:SS  

---

# 🧰 Features

- Bulk ticket updates  
- SLA (TTR / TTO) calculations  
- SQL preview  
- No DB triggers required  
- Multi-ticket support  

---

# 🛠 Requirements

streamlit  
mysql-connector-python  
pandas  
openpyxl  

---

# 📜 License

MIT License  
https://choosealicense.com/licenses/mit/
