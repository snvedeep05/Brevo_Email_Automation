# Brevo Email Automation

A Streamlit-based transactional email automation tool that sends Brevo template emails to shortlisted, rejected, and assignment candidates. Connected to a shared Neon PostgreSQL database for duplicate prevention and full email audit logging.

---

## Recent Updates

### March 2026

#### 1. Neon PostgreSQL Integration — Duplicate Email Prevention
**Why:** There was no record of which emails had been sent. Re-uploading the same Excel or clicking Send again would fire duplicate emails to the same candidates.

**Fix:** Connected the app to the shared Neon PostgreSQL database. Created the `email_logs` table with a `UNIQUE(email, template_id)` constraint. Every send is checked against this table before calling the Brevo API, and logged after a confirmed successful send.

**Impact:** The same candidate can never receive the same email type twice, regardless of how many times the Excel is uploaded or the send button is clicked.

---

#### 2. Dashboard Tab Added
**Why:** There was no visibility into how many emails had been sent, to whom, or which type. No audit trail existed.

**Fix:** Added a third tab — **Dashboard** — that reads live from the `email_logs` table and shows:
* 4 metric cards: Total Sent, Shortlisted, Rejected, Assignment
* Bar chart of emails by type
* Filterable log table (Name, Email, Type, Job Title, Sent At)
* CSV export button for the filtered view

---

#### 3. Detailed Skip Reporting in Send Tabs
**Why:** Previously only a count was shown after sending (e.g. "Skipped: 3"). Recruiters had no way to know which specific candidates were skipped and why.

**Fix:** Both Tab 1 and Tab 2 now collect per-entry detail on every skipped or already-sent candidate. After send completes, each entry is listed with name, email, and the reason (invalid email / unknown decision / send failed / already sent).

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Application](#application)
  - [Login Page](#login-page)
  - [Tab 1 — Shortlisting Emails](#tab-1--shortlisting-emails)
  - [Tab 2 — Assignment Emails](#tab-2--assignment-emails)
  - [Tab 3 — Dashboard](#tab-3--dashboard)
- [Source Modules](#source-modules)
  - [src/brevo\_client.py](#srcbrevo_clientpy)
  - [src/db\_client.py](#srcdb_clientpy)
- [Brevo Email Templates](#brevo-email-templates)
- [Send Flow](#send-flow)
- [Duplicate Prevention Logic](#duplicate-prevention-logic)
- [Configuration](#configuration)
- [Installation & Running](#installation--running)

---

## Overview

This tool allows a recruiter to:

1. Upload an Excel file of reviewed candidates (with a `decision` column)
2. Send **shortlist** or **rejection** emails automatically via Brevo transactional templates
3. Send **assignment** emails to interested candidates with a dynamically computed deadline
4. Prevent duplicate sends — the same `email + template` combination is **never sent twice**
5. View a live **Dashboard** of all sent emails with metrics, bar chart, filter, and CSV export

---

## Architecture

```
┌────────────────────────────────────────────────────┐
│              STREAMLIT APP (app.py)                │
│   Login → Tab 1: Shortlisting → Tab 2: Assignment  │
│                → Tab 3: Dashboard                  │
└──────────────┬────────────────┬───────────────────┘
               │                │
┌──────────────▼──────┐  ┌──────▼──────────────────┐
│  src/brevo_client   │  │   src/db_client.py       │
│  BrevoClient class  │  │   EmailLog ORM model     │
│  Brevo Python SDK   │  │   SQLAlchemy + Neon PG   │
└──────────────┬──────┘  └──────┬──────────────────┘
               │                │
┌──────────────▼──────┐  ┌──────▼──────────────────┐
│   Brevo API         │  │   Neon PostgreSQL         │
│   (Transactional    │  │   email_logs table        │
│    Email Service)   │  │   (shared with Resume     │
└─────────────────────┘  │    Screening backend)     │
                         └──────────────────────────┘
```

**Key design decision:** The Neon PostgreSQL database is shared between this app and the Resume Screening backend. The `email_logs` table lives in the same database so both systems reference the same candidate data — enabling future pipeline automation between the two tools.

---

## Project Structure

```
Brevo_Email_Automation/
├── app.py                  # Streamlit UI — login + all 3 tabs
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Python version config (3.11)
└── src/
    ├── brevo_client.py     # Brevo API wrapper — sends transactional emails
    └── db_client.py        # DB connection, EmailLog model, helper functions
```

---

## Database Schema

### `email_logs`

Stores a record of every successfully sent email. Acts as the deduplication source — before any email is sent, this table is checked.

| Column | Type | Description |
|--------|------|-------------|
| log_id | Integer | Primary key, auto-increment |
| email | Text | Recipient email address |
| template_id | Integer | Brevo template ID used (28, 36, or 30) |
| full_name | Text | Recipient full name (nullable) |
| job_title | Text | Job title context (nullable) |
| sent_at | Timestamp | Auto-set to DB server time on insert |

**Unique constraint:** `UNIQUE(email, template_id)` — enforced at the database level.

This means:
- The same person **can** receive a shortlist email (28) AND an assignment email (30)
- The same person **cannot** receive the same template type twice, ever
- Even if the app-level check is bypassed, the DB constraint is the final guard

> `email_logs` lives in the same Neon PostgreSQL instance used by the Resume Screening backend. The `DATABASE_URL` secret must point to that shared connection string.

---

## Application

### Login Page

**`app.py`**

A credential gate rendered before the main app.

- Username and password read from `st.secrets["APP_USERNAME"]` and `st.secrets["APP_PASSWORD"]`
- Session state key: `st.session_state.logged_in`
- Company logo loaded from `st.secrets["COMPANY_LOGO"]` — displayed fixed at top-left
- Login form is center-aligned using a 3-column layout (`[2, 1.2, 2]`)
- On success → sets `logged_in = True` and reruns
- On failure → shows `st.error("Invalid credentials")`
- `st.stop()` prevents the rest of the app from rendering if not logged in

---

### Tab 1 — Shortlisting Emails

Sends shortlist or rejection emails based on a `decision` column in the uploaded Excel.

**Required Excel columns:**

| Column | Expected values |
|--------|----------------|
| `full_name` | Candidate's full name |
| `email` | Candidate's email address |
| `decision` | `shortlisted` or `rejected` (case-insensitive) |
| `job_title` | Job role the candidate applied for |

**Pre-send preview shown:**
- Full data table
- Metric cards: Shortlisted count | Rejected count

**Send flow per row:**

```
1. Validate email format (email-validator library)
   → Invalid → add to skipped_list, continue

2. Map decision → template_id
   "shortlisted" → 28
   "rejected"    → 36
   anything else → add to skipped_list, continue

3. Check is_already_sent(db, email, template_id)
   → Already sent → add to already_sent_list, continue

4. BrevoClient.send_template_email(
       params: { FIRSTNAME: name, JOB_TITLE: job_title }
   )
   → API failure → add to skipped_list

5. log_email_sent(db, email, template_id, full_name, job_title)
   → INSERT into email_logs
   → sent += 1
```

**Post-send output:**
```
✅ Done — N email(s) sent successfully.
⏩ Already sent (skipped): N
   • Name — email
⏭ Skipped / Failed: N
   • Name — email (reason)
```

---

### Tab 2 — Assignment Emails

Sends assignment emails to candidates using a single fixed template (ID 30).

**Required Excel columns:**

| Column | Description |
|--------|-------------|
| `full_name` | Candidate's full name |
| `email` | Candidate's email address |

**Key behaviour:**
- `first_name` is extracted as `name.split()[0]`
- `deadline_date` is computed at send time as `today + 10 days` (formatted as `DD Month YYYY`) and injected as `{{ DEADLINE_DATE }}` into the template
- Uses the same duplicate check + logging pattern as Tab 1

**Send flow per row:**

```
1. Validate email format
   → Invalid → skip

2. Check is_already_sent(db, email, template_id=30)
   → Already sent → skip

3. BrevoClient.send_template_email(
       params: { FIRSTNAME: first_name, DEADLINE_DATE: deadline_date }
   )

4. log_email_sent(db, email, 30, full_name)
```

---

### Tab 3 — Dashboard

Queries `email_logs` live on every page load and renders a full email audit view.

**Components:**

1. **Metrics row** — 4 cards:
   - Total Sent | Shortlisted | Rejected | Assignment

2. **Bar chart** — `st.bar_chart` of email count by type

3. **Filter dropdown** — All / Shortlisted / Rejected / Assignment

4. **Log table** — Name, Email, Type, Job Title, Sent At (most recent first)

5. **CSV export** — Downloads the currently filtered view as `email_log_export.csv`

---

## Source Modules

### `src/brevo_client.py`

**`BrevoClient` class** — wraps the `brevo-python` SDK.

**Initialization** — reads from `st.secrets`:
- `BREVO_API_KEY` — Brevo API key
- `BREVO_SENDER_EMAIL` — sender email address
- `BREVO_SENDER_NAME` — sender display name (defaults to `"AppWeave Labs"`)

Configures `brevo_python.TransactionalEmailsApi` as `self.email_api`.

---

**`send_template_email(to_email, template_id, params, to_name, sender_email, sender_name, attachments)`**

| Argument | Type | Description |
|----------|------|-------------|
| `to_email` | str | Recipient email |
| `template_id` | int | Brevo template ID |
| `params` | dict | Template placeholder values e.g. `{"FIRSTNAME": "Riya"}` |
| `to_name` | str | Recipient display name (optional) |
| `sender_email` | str | Override sender email (optional) |
| `sender_name` | str | Override sender name (optional) |
| `attachments` | list | `[{"name": ..., "content": base64}]` (optional) |

Returns `True` on success, `False` on `ApiException`.

**Template syntax note:**

Brevo templates support two syntaxes:
- `{{ FIRSTNAME }}` — params passed directly via the `params` field ✅ used here
- `{{ contact.FIRSTNAME }}` — requires the recipient to exist as a Brevo contact with that attribute set

If a template uses `{{ contact.* }}` and the recipient is not in Brevo contacts, the API returns `"params is blank"`. The client prints a troubleshooting guide in this case.

---

### `src/db_client.py`

Handles all database interaction — model definition, session management, and query helpers.

**`EmailLog` — SQLAlchemy ORM model**

```python
class EmailLog(Base):
    __tablename__ = "email_logs"
    log_id      = Column(Integer, primary_key=True)
    email       = Column(Text, nullable=False)
    template_id = Column(Integer, nullable=False)
    full_name   = Column(Text)
    job_title   = Column(Text)
    sent_at     = Column(TIMESTAMP, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("email", "template_id", name="uq_email_template"),
    )
```

---

**`get_engine()`**

Creates a SQLAlchemy engine from `st.secrets["DATABASE_URL"]` with `pool_pre_ping=True`. The pre-ping issues a lightweight check before each connection is handed from the pool — prevents `SSL connection closed unexpectedly` errors from Neon's idle connection timeout.

---

**`get_session()`**

Calls `get_engine()`, runs `Base.metadata.create_all()` to ensure the `email_logs` table exists (idempotent — safe to call on every request), returns an open SQLAlchemy `Session`.

---

**`is_already_sent(db, email, template_id) → bool`**

Queries `email_logs` for a row matching both `email` AND `template_id`. Returns `True` if found. Called before every send.

---

**`log_email_sent(db, email, template_id, full_name, job_title)`**

Inserts a new `EmailLog` row and commits. Called only after a confirmed successful Brevo API response.

---

**`get_all_logs(db) → list[dict]`**

Returns all rows from `email_logs` ordered by `sent_at DESC` as a list of dicts. Used by the Dashboard tab.

---

## Brevo Email Templates

| Template ID | Purpose | Params injected |
|-------------|---------|-----------------|
| 28 | Shortlisted notification | `FIRSTNAME`, `JOB_TITLE` |
| 36 | Rejected notification | `FIRSTNAME`, `JOB_TITLE` |
| 30 | Assignment email with deadline | `FIRSTNAME`, `DEADLINE_DATE` |

Constants defined at the top of `app.py`:

```python
TEMPLATE_SHORTLISTED = 28
TEMPLATE_REJECTED    = 36
TEMPLATE_ASSIGNMENT  = 30
```

---

## Send Flow

Full end-to-end flow for a single candidate row:

```
Excel row (name, email, decision, job_title)
        │
        ▼
1. Validate email format (email-validator)
   → Invalid → skip, log reason
        │
        ▼
2. Map decision → template_id
   "shortlisted" → 28  |  "rejected" → 36  |  other → skip
        │
        ▼
3. Check DB: is_already_sent(email, template_id)?
   → Yes → skip, log as already_sent
        │
        ▼
4. BrevoClient.send_template_email(
       to_email, template_id, params, to_name
   )
   → ApiException → skip, log reason
        │
        ▼
5. log_email_sent(email, template_id, full_name, job_title)
   → INSERT into email_logs
   → DB UNIQUE constraint is the final guard
        │
        ▼
6. sent += 1
```

---

## Duplicate Prevention Logic

Two layers protect against duplicate sends:

**Layer 1 — App-level check (before send):**
`is_already_sent()` queries `email_logs` before calling the Brevo API. If `(email, template_id)` already exists, the row is skipped — no API call is made, no Brevo credit consumed.

**Layer 2 — DB-level constraint (on insert):**
`UNIQUE(email, template_id)` on the `email_logs` table. Even if two requests bypass the app-level check simultaneously, the database will reject the second insert with a constraint violation.

**What counts as a duplicate:**

Same `email` + same `template_id`. This means:
- `riya@example.com` + template 28 (shortlisted) → logged once, never resent
- `riya@example.com` + template 30 (assignment) → separate entry, allowed

A candidate can move through the pipeline — shortlisted then assignment — while being fully protected from receiving any single stage twice.

---

## Configuration

### `.streamlit/secrets.toml`

```toml
APP_USERNAME        = "admin"
APP_PASSWORD        = "your_password"
COMPANY_LOGO        = "https://your-logo-url.png"

BREVO_API_KEY       = "xkeysib-..."
BREVO_SENDER_EMAIL  = "hr@yourcompany.com"
BREVO_SENDER_NAME   = "AppWeave Labs"

DATABASE_URL        = "postgresql://user:password@host/dbname"
```

> `DATABASE_URL` must be the same Neon PostgreSQL connection string used by the Resume Screening backend.

---

## Installation & Running

### Local

```bash
pip install -r requirements.txt

# Create .streamlit/secrets.toml with required variables (see above)

streamlit run app.py
```

### Streamlit Cloud

1. Push to GitHub
2. Connect repo in Streamlit Cloud dashboard
3. Go to **App Settings → Secrets** → paste the `secrets.toml` content
4. Deploy — no additional config needed

### Dependencies

| Package | Purpose |
|---------|---------|
| streamlit | UI framework |
| pandas | Excel parsing and data manipulation |
| brevo-python==1.2.0 | Official Brevo API SDK |
| email-validator | Email format validation before send |
| sqlalchemy | ORM for PostgreSQL |
| psycopg2-binary | PostgreSQL driver |
| openpyxl | Reading `.xlsx` files |
| requests | HTTP utility |
| python-dotenv | Env variable support |
