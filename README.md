# 🎫 UPCL Ticket Update Tool

A Python-based tool to update ticket data in the UPCL system.

---

## 📦 Requirements

- Python 3.8+
- MySQL access (credentials required)

---

## ⚙️ Installation

### 1. Clone Repository

```bash
git clone https://github.com/NAMANNIMBLE1/upcl_backend_script.git
cd upcl_backend_script
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
```

#### Activate Environment

**Windows**
```bash
.venv\Scripts\activate
```

**Linux / Mac**
```bash
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🗄️ Database Configuration

Update DB credentials inside:

- `update_2input.py`
- `update_4input.py`
- `app.py` (via CONFIG import)

```python
CONFIG = {
    "host": "your_host",
    "user": "your_user",
    "password": "your_password",
    "database": "your_database",
}
```

---

## ▶️ How to Run

### 🔹 1. Streamlit UI (Recommended)

```bash
streamlit run app.py
```

> Opens a browser-based UI for interactive use.

### 🔹 2. CLI Scripts

**2-Input Script**
```bash
python update_2input.py
```

**4-Input Script**
```bash
python update_4input.py
```

---

## 🧠 How to Use

### 🔹 Streamlit UI

1. Select mode: **2-Input** or **4-Input**
2. Fill in the required details
3. Click **➕ Add to Queue**
4. Click **⚙️ Generate SQL Preview**
5. Review the generated SQL
6. Click **✅ Confirm & Execute**

---

### 🔹 2-Input Mode

**Inputs:**
- Ticket Ref
- Resolution Date
- Resolution Time

**Use when:**
- Only closing a ticket
- No category changes needed

---

### 🔹 4-Input Mode

**Inputs:**
- Ticket Ref
- Category
- Subcategory
- Resolution Date
- Resolution Time

**Use when:**
- Need to update category/subcategory
- Also closing the ticket

---

### 🔹 CLI Usage

**2-Input**
```bash
python update_2input.py
```
- Enter ticket ref
- Enter resolution time
- Confirm execution

**4-Input**
```bash
python update_4input.py
```
- Enter ticket ref
- Enter category
- Enter subcategory
- Enter resolution time
- Confirm execution

---

## ⚠️ Important Notes

- Changes are **permanent** — always verify before execution
- Time format must be: `YYYY-MM-DD HH:MM:SS`
- Category & subcategory must match values in the database

---

## 🧰 Features

- Ticket updates
- SLA recalculation
- SQL preview before execution
- Queue support (UI mode)
- CLI + UI support

---

## 📜 License

[MIT License](https://choosealicense.com/licenses/mit/)
