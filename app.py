import streamlit as st
import pandas as pd
from src.brevo_client import BrevoClient
from email_validator import validate_email, EmailNotValidError
from datetime import datetime, timedelta

st.set_page_config(page_title="Email Automation", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

COMPANY_LOGO = st.secrets["COMPANY_LOGO"]
APP_USERNAME = st.secrets["APP_USERNAME"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]

# ---------------- LOGIN PAGE ----------------

def login_page():

    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 8.5rem;
        }

        .company-header {
            display: flex;
            align-items: center;
            gap: 12px;
            position: fixed;
            top: 1.2rem;
            left: 1.8rem;
            margin-bottom: 0;
            z-index: 1000;
        }

        .company-name {
            font-size: 20px;
            font-weight: 600;
            color: #1f2937;
        }

        .login-title {
            font-size: 40px;
            font-weight: 700;
            margin-bottom: 2rem;
            color: #111827;
        }

        [data-testid="stHeader"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="company-header">
            <img src="{COMPANY_LOGO}" width="45">
            <div class="company-name">Appweave Labs</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([2, 1.2, 2])

    with col2:

        st.markdown(
            '<div class="login-title">🔐 Resume Screening</div>',
            unsafe_allow_html=True
        )

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):

            if username == APP_USERNAME and password == APP_PASSWORD:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid credentials")


if not st.session_state.logged_in:
    login_page()
    st.stop()


# ---------------- TEMPLATE IDS ----------------

TEMPLATE_SHORTLISTED = 28
TEMPLATE_REJECTED = 36
TEMPLATE_ASSIGNMENT = 30


# ---------------- TABS ----------------

tab1, tab2 = st.tabs([
    "📧 Shortlisting Emails",
    "📝 Assignment Emails"
])


# ====================================================
# TAB 1 – SHORTLIST / REJECTION EMAILS
# ====================================================

with tab1:

    st.subheader("📧 Send Shortlisting / Rejection Emails")

    uploaded_excel = st.file_uploader(
        "Upload reviewed Excel file",
        type=["xlsx"],
        key="shortlist_upload"
    )

    if uploaded_excel:

        df = pd.read_excel(uploaded_excel)

        required_cols = ["full_name", "email", "decision", "job_title"]

        missing = [c for c in required_cols if c not in df.columns]

        if missing:
            st.error(f"Missing required columns: {missing}")
            st.stop()

        df = df.rename(columns={
            "full_name": "Name",
            "email": "Email",
            "decision": "Decision",
            "job_title": "Job_Title"
        })

        df = df.drop_duplicates(subset=["Email"])

        if df.empty:
            st.warning("⚠️ Uploaded Excel has no rows to process.")
            st.stop()

        st.dataframe(df, use_container_width=True)

        st.markdown("### 📊 Decision Summary")

        counts = df["Decision"].value_counts()

        col1, col2 = st.columns(2)

        col1.metric("Shortlisted", counts.get("shortlisted", 0))
        col2.metric("Rejected", counts.get("rejected", 0))


        if st.button("🚀 Send Emails"):

            client = BrevoClient()

            sent = 0
            skipped = 0

            progress = st.progress(0)

            for i, row in df.iterrows():

                name = str(row["Name"]).strip()
                email = str(row["Email"]).strip()
                decision = str(row["Decision"]).strip().lower()
                job_title = str(row["Job_Title"]).strip()

                try:
                    email = validate_email(email).email
                except EmailNotValidError:
                    skipped += 1
                    continue

                if decision == "shortlisted":
                    template_id = TEMPLATE_SHORTLISTED
                elif decision == "rejected":
                    template_id = TEMPLATE_REJECTED
                else:
                    skipped += 1
                    continue

                success = client.send_template_email(
                    to_email=email,
                    template_id=template_id,
                    params={
                        "FIRSTNAME": name,
                        "JOB_TITLE": job_title
                    },
                    to_name=name
                )

                if success:
                    sent += 1
                else:
                    skipped += 1

                progress.progress((i + 1) / len(df))

            st.success(f"✅ Emails sent: {sent}")
            st.warning(f"⏭ Skipped / Failed: {skipped}")


# ====================================================
# TAB 2 – ASSIGNMENT EMAILS
# ====================================================

with tab2:

    st.subheader("📝 Send Assignment Emails")

    uploaded_excel = st.file_uploader(
        "Upload Excel with interested candidates",
        type=["xlsx"],
        key="assignment_upload"
    )

    if uploaded_excel:

        df = pd.read_excel(uploaded_excel)

        required_cols = ["name", "email"]

        missing = [c for c in required_cols if c not in df.columns]

        if missing:
            st.error(f"Missing required columns: {missing}")
            st.stop()

        df = df.drop_duplicates(subset=["email"])

        if df.empty:
            st.warning("⚠️ Excel has no valid rows.")
            st.stop()

        st.markdown("### 📋 Candidate Preview")

        st.dataframe(df, use_container_width=True)

        st.markdown(f"Total candidates: **{len(df)}**")

        if st.button("🚀 Send Assignment Emails"):

            client = BrevoClient()

            sent = 0
            skipped = 0

            deadline_date = (datetime.today() + timedelta(days=10)).strftime("%d %B %Y")
            
            progress = st.progress(0)

            for i, row in df.iterrows():

                name = str(row["name"]).strip()
                email = str(row["email"]).strip()

                first_name = name.split()[0]

                try:
                    email = validate_email(email).email
                except EmailNotValidError:
                    skipped += 1
                    continue

                success = client.send_template_email(
                    to_email=email,
                    template_id=TEMPLATE_ASSIGNMENT,
                    params={
                        "FIRSTNAME": first_name,
                        "DEADLINE_DATE": deadline_date
                    },
                    to_name=name
                )

                if success:
                    sent += 1
                else:
                    skipped += 1

                progress.progress((i + 1) / len(df))

            st.success(f"✅ Assignment emails sent: {sent}")
            st.warning(f"⏭ Skipped / Failed: {skipped}")
