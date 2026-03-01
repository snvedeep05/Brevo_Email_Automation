import streamlit as st
import pandas as pd
from brevo_client import BrevoClient

st.set_page_config(page_title="Email Automation", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

COMPANY_LOGO = st.secrets["COMPANY_LOGO"]
APP_USERNAME = st.secrets["APP_USERNAME"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]

def login_page():

    st.markdown(
        """
        <style>
        /* Add breathing room at the top of the login page */
        .block-container {
            padding-top: 8.5rem;
        }

        /* Company header */
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
            font-size: 35px;
            font-weight: 700;
            line-height: 1.1;
            margin-bottom: 2rem;
            color: #111827;
        }

        

        /* Hide weird top header block */
        [data-testid="stHeader"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ---------------- COMPANY LOGO + NAME ----------------
    st.markdown(
        f"""
        <div class="company-header">
            <img src="{COMPANY_LOGO}" width="45">
            <div class="company-name">Appweave Labs</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ---------------- CENTER LOGIN ----------------
    col1, col2, col3 = st.columns([2, 1.2, 2])

    with col2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)

        st.markdown(
            '<div class="login-title">🔐 Brevo Mail Automation</div>',
            unsafe_allow_html=True
        )

        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("Login", use_container_width=True):
            if username == APP_USERNAME and password == APP_PASSWORD:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid credentials")

        st.markdown("</div>", unsafe_allow_html=True)



if not st.session_state.logged_in:
    login_page()
    st.stop()
    
# Template mapping
TEMPLATE_SHORTLISTED = 28   # success template
TEMPLATE_REJECTED = 36      # rejection template

st.subheader("📧 Send Emails from Excel")

uploaded_excel = st.file_uploader(
    "Upload reviewed Excel file",
    type=["xlsx"]
)

if uploaded_excel:
    df = pd.read_excel(uploaded_excel)

    # Required columns from new Excel format
    required_cols = ["full_name", "email", "decision", "job_title"]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        st.error(f"Missing required columns: {missing}")
        st.stop()

    # Rename for internal consistency
    df = df.rename(columns={
        "full_name": "Name",
        "email": "Email",
        "decision": "Decision",
        "job_title": "Job_Title"
    })

    if df.empty:
        st.warning("⚠️ Uploaded Excel has no rows to process.")
        st.stop()

    st.dataframe(df, use_container_width=True)

    # Decision summary (clean metrics)
    st.markdown("### 📊 Decision Summary")
    
    counts = df["Decision"].value_counts()
    
    col1, col2 = st.columns(2)
    col1.metric("Shortlisted", counts.get("shortlisted", 0))
    col2.metric("Rejected", counts.get("rejected", 0))


    if st.button("🚀 Send Emails"):
        client = BrevoClient()
        sent, skipped = 0, 0

        for _, row in df.iterrows():
            name = str(row["Name"]).strip()
            email = str(row["Email"]).strip()
            decision = str(row["Decision"]).strip().lower()
            job_title = str(row["Job_Title"]).strip()

            # Validate email
            if not email or "@" not in email:
                skipped += 1
                continue

            # ✅ Decision logic updated
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

        st.success(f"✅ Emails sent: {sent} | ⏭ Skipped/Failed: {skipped}")    
