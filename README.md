# Playto Payout Engine 🚀

A highly reliable, production-ready payout system built for the Playto Founding Engineer Challenge. 

This engine enforces strict financial integrity using a **ledger-based accounting system**, **row-level concurrency locks**, and **strict idempotency** to prevent race conditions and duplicate payouts. A background Celery worker handles simulated bank delays, while a React dashboard provides real-time polling updates.

##  Tech Stack
* **Backend:** Django, Django REST Framework
* **Database:** PostgreSQL (with `select_for_update` row-level locks)
* **Background Worker:** Celery + Redis (Upstash)
* **Frontend:** React, Vite, TailwindCSS, Lucide Icons

---

## Quick Start Guide

### 1. Prerequisites
* Python 3.10+
* Node.js 18+
* PostgreSQL (or Docker to run it locally)
* Redis (or Docker to run it locally)

### 2. Environment Setup
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgres://playtouser:playtopass123@localhost:5432/playtodb
CELERY_BROKER_URL=redis://localhost:6379/0
```

*(Note: If you don't have Postgres and Redis installed on your machine, simply run `docker-compose up -d` in the root folder!)*

### 3. Backend Setup
Open a terminal in the root folder (`playto-task`):
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Run migrations to set up PostgreSQL
python manage.py makemigrations
python manage.py migrate

# Seed the database with a test merchant
python seed_data.py
```
*(Copy the generated `MERCHANT_ID` from the output into `frontend/src/App.tsx` on line 6).*

### 4. Running the Application (Requires 3 Terminals)

**Terminal 1: Django API Server**
```bash
.\venv\Scripts\activate
python manage.py runserver
```

**Terminal 2: Celery Background Worker**
```bash
.\venv\Scripts\activate
python -m celery -A backend worker -l info -P eventlet
```

**Terminal 3: React Dashboard**
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173** in your browser.

---

## 🧪 Testing & Utilities

### Automated Tests
Run the concurrency and idempotency tests:
```bash
.\venv\Scripts\activate
python manage.py test api -v 2
```

### Utility Scripts
We included a helpful script to interact with the system without using the UI:

**1. Credit a Merchant's Account**
Instantly add money to the merchant's available balance and create the required ledger entry:
```bash
python credit_account.py
```


---

##  Project Structure
* `api/models.py` — Core database architecture (Merchant, Payout, LedgerEntry).
* `api/views.py` — Idempotent, concurrency-locked API endpoints.
* `api/tasks.py` — Celery state machine simulating a bank (70% success, 20% fail, 10% hang).
* `frontend/src/App.tsx` — React dashboard with auto-polling.
* `EXPLAINER.md` — Detailed answers to the architectural design questions.
