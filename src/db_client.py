import streamlit as st
from sqlalchemy import create_engine, Column, Integer, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()


class EmailLog(Base):
    __tablename__ = "email_logs"

    log_id = Column(Integer, primary_key=True)
    email = Column(Text, nullable=False)
    template_id = Column(Integer, nullable=False)
    full_name = Column(Text)
    job_title = Column(Text)
    sent_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("email", "template_id", name="uq_email_template"),
    )


def get_engine():
    database_url = st.secrets["DATABASE_URL"]
    return create_engine(database_url, pool_pre_ping=True)


def get_session():
    engine = get_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def is_already_sent(db, email: str, template_id: int) -> bool:
    return db.query(EmailLog).filter_by(
        email=email,
        template_id=template_id
    ).first() is not None


def log_email_sent(db, email: str, template_id: int, full_name: str = None, job_title: str = None):
    db.add(EmailLog(
        email=email,
        template_id=template_id,
        full_name=full_name,
        job_title=job_title
    ))
    db.commit()


def get_all_logs(db) -> list:
    rows = db.query(EmailLog).order_by(EmailLog.sent_at.desc()).all()
    return [
        {
            "log_id": r.log_id,
            "full_name": r.full_name,
            "email": r.email,
            "template_id": r.template_id,
            "job_title": r.job_title,
            "sent_at": r.sent_at,
        }
        for r in rows
    ]
