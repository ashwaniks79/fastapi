from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, TIMESTAMP, 
    ForeignKey, ARRAY, JSON, UniqueConstraint
)
from sqlalchemy.sql import func, expression
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

# -------------------------
# USERS TABLE
# -------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(String(16), unique=True, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    company_information_page_files = Column(JSON, server_default='[]')  # safer default
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    phone_number = Column(String, nullable=False)
    country = Column(String, nullable=False)
    timezone = Column(String, nullable=False)
    subscription_plan = Column(String, nullable=False, server_default="free")

    is_verified = Column(Boolean, nullable=False, server_default=expression.false())
    role = Column(String, nullable=False, server_default="customer")
    permissions = Column(ARRAY(String), nullable=False, server_default=expression.text("ARRAY['read']"))

    otp_code = Column(String, nullable=True)
    otp_verified = Column(Boolean, nullable=False, server_default=expression.false())
    otp_attempts = Column(Integer, nullable=False, server_default="0")
    otp_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    otp_created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=True)

    access_token = Column(String, nullable=True)
    stripe_customer_id = Column(String, unique=True, nullable=True)

    company_info = relationship("CompanyInformationPageDetails", back_populates="user", uselist=False)
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    trial_start_date = Column(DateTime(timezone=True), nullable=True)
    trial_expiry_date = Column(DateTime(timezone=True), nullable=True)


# -------------------------
# COMPANY INFORMATION TABLE
# -------------------------
class CompanyInformationPageDetails(Base):
    __tablename__ = "company_information_page_details"
    __table_args__ = (UniqueConstraint('user_id'),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String(16), ForeignKey("users.id"), nullable=False)

    company_name = Column(String, nullable=False)
    business_reg_number = Column(String, nullable=False)
    industry_type = Column(String, nullable=False)
    other_industry = Column(String, nullable=True)
    num_employees = Column(Integer, nullable=True)
    company_website = Column(String, nullable=True)
    business_phone = Column(String, nullable=False)
    business_email = Column(String, nullable=False)

    address_street = Column(String, nullable=False)
    address_city = Column(String, nullable=False)
    address_state = Column(String, nullable=False)
    address_postcode = Column(String, nullable=False)
    address_country = Column(String, nullable=False)

    company_logo_path = Column(String, nullable=True)
    registration_doc_path = Column(String, nullable=False)
    additional_files_paths = Column(ARRAY(String), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    terms_accepted = Column(Boolean, nullable=False, server_default=expression.false())

    user = relationship("User", back_populates="company_info")


# -------------------------
# SUBSCRIPTION TABLE
# -------------------------
class Subscription(Base):
    __tablename__ = "subscriptions"

    subscription_id = Column(String, ForeignKey("users.id"), primary_key=True)
    subscriptions_plan = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)

    auto_renew = Column(Boolean, nullable=False, server_default=expression.true())
    active = Column(Boolean, nullable=False, server_default=expression.true())

    # Usage tracking
    trial_used = Column(Boolean, nullable=False, server_default=expression.false())  # 5-day free trial
    projects_used = Column(Integer, nullable=False, server_default="0")               # Track active projects
    documents_uploaded = Column(Integer, nullable=False, server_default="0")          # Track uploaded docs
    queries_made = Column(Integer, nullable=False, server_default="0")                # Track AI queries used

    # Optional: store which features are unlocked
    features_enabled = Column(ARRAY(String), nullable=True)

    user = relationship("User", back_populates="subscription")
