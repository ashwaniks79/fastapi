# from sqlalchemy import (
#     Column, Integer, String, Boolean, DateTime, TIMESTAMP, 
#     ForeignKey, ARRAY, JSON, UniqueConstraint,Float, Text
# )
# from sqlalchemy.sql import func, expression
# from sqlalchemy.orm import relationship
# from .database import Base
# from datetime import datetime

# # -------------------------
# # USERS TABLE
# # -------------------------
# class User(Base):
#     __tablename__ = "users"

#     id = Column(String(16), unique=True, primary_key=True, index=True)
#     first_name = Column(String, nullable=False)
#     last_name = Column(String, nullable=False)
#     username = Column(String, unique=True, nullable=False)
#     email = Column(String, unique=True, index=True, nullable=False)
#     hashed_password = Column(String, nullable=False)
#     company_name = Column(String, nullable=False)
#     company_information_page_files = Column(JSON, server_default='[]')  # safer default
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     phone_number = Column(String, nullable=False)
#     country = Column(String, nullable=False)
#     timezone = Column(String, nullable=False)
#     subscription_plan = Column(String, nullable=False, server_default="free")

#     is_verified = Column(Boolean, nullable=False, server_default=expression.false())
#     role = Column(String, nullable=False, server_default="customer")
#     permissions = Column(ARRAY(String), nullable=False, server_default=expression.text("ARRAY['read']"))

#     otp_code = Column(String, nullable=True)
#     otp_verified = Column(Boolean, nullable=False, server_default=expression.false())
#     otp_attempts = Column(Integer, nullable=False, server_default="0")
#     otp_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
#     otp_created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=True)

#     access_token = Column(String, nullable=True)
#     stripe_customer_id = Column(String, unique=True, nullable=True)

#     company_info = relationship("CompanyInformationPageDetails", back_populates="user", uselist=False)
#     subscription = relationship("Subscription", back_populates="user", uselist=False)
#     trial_start_date = Column(DateTime(timezone=True), nullable=True)
#     trial_expiry_date = Column(DateTime(timezone=True), nullable=True)


# # -------------------------
# # COMPANY INFORMATION TABLE
# # -------------------------
# class CompanyInformationPageDetails(Base):
#     __tablename__ = "company_information_page_details"
#     __table_args__ = (UniqueConstraint('user_id'),)

#     id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
#     user_id = Column(String(16), ForeignKey("users.id"), nullable=False)

#     company_name = Column(String, nullable=False)
#     business_reg_number = Column(String, nullable=False)
#     industry_type = Column(String, nullable=False)
#     other_industry = Column(String, nullable=True)
#     num_employees = Column(Integer, nullable=True)
#     company_website = Column(String, nullable=True)
#     business_phone = Column(String, nullable=False)
#     business_email = Column(String, nullable=False)

#     address_street = Column(String, nullable=False)
#     address_city = Column(String, nullable=False)
#     address_state = Column(String, nullable=False)
#     address_postcode = Column(String, nullable=False)
#     address_country = Column(String, nullable=False)

#     company_logo_path = Column(String, nullable=True)
#     registration_doc_path = Column(String, nullable=False)
#     additional_files_paths = Column(ARRAY(String), nullable=True)

#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

#     terms_accepted = Column(Boolean, nullable=False, server_default=expression.false())

#     user = relationship("User", back_populates="company_info")


# # -------------------------
# # SUBSCRIPTION TABLE
# # -------------------------
# class Subscription(Base):
#     __tablename__ = "subscriptions"

#     subscription_id = Column(String, ForeignKey("users.id"), primary_key=True)
#     subscriptions_plan = Column(String, nullable=False)
#     start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
#     end_date = Column(DateTime, nullable=True)
#     auto_renew = Column(Boolean, nullable=False, server_default=expression.true())
#     active = Column(Boolean, nullable=False, server_default=expression.true())
#     # Usage tracking
#     trial_used = Column(Boolean, nullable=False, server_default=expression.false())  # 5-day free trial
#     projects_used = Column(Integer, nullable=False, server_default="0")               # Track active projects
#     documents_uploaded = Column(Integer, nullable=False, server_default="0")          # Track uploaded docs
#     queries_made = Column(Integer, nullable=False, server_default="0")                # Track AI queries used
#     features_enabled = Column(ARRAY(String), nullable=True)
#     user = relationship("User", back_populates="subscription")

# # -------------------------
# # Upload Document Table
# # -------------------------
# class Document(Base):
#     __tablename__ = "documents"
#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(String(16), ForeignKey("users.id"), nullable=False, index=True)
#     filename = Column(String, nullable=False)
#     content_type = Column(String, nullable=False)
#     size = Column(Integer, nullable=False)
#     storage_key = Column(String, nullable=False)     # key/path in DO Spaces
#     url = Column(String, nullable=True)
#     uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
#     deleted = Column(Boolean, nullable=False, server_default=expression.false())

#     chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

# #--------------------------------------------------
# # -- DocumentChunk table for provenance + vector id mapping
# #--------------------------------------------------

# class DocumentChunk(Base):
#     __tablename__ = "document_chunks"
#     id = Column(Integer, primary_key=True, index=True)
#     document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
#     chunk_index = Column(Integer, nullable=False)
#     text = Column(Text, nullable=False)               # small excerpt/pieces of text
#     vector_id = Column(String, nullable=True, index=True)  # id in vector DB
#     created_at = Column(DateTime(timezone=True), server_default=func.now())

#     document = relationship("Document", back_populates="chunks")
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, TIMESTAMP, 
    ForeignKey, ARRAY, JSON, UniqueConstraint, Float, Text
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
    company_information_page_files = Column(JSON, server_default='[]')
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

    company_info = relationship(
        "CompanyInformationPageDetails",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    subscription = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    documents = relationship(
        "Document",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    trial_start_date = Column(DateTime(timezone=True), nullable=True)
    trial_expiry_date = Column(DateTime(timezone=True), nullable=True)


# -------------------------
# COMPANY INFORMATION TABLE
# -------------------------
class CompanyInformationPageDetails(Base):
    __tablename__ = "company_information_page_details"
    __table_args__ = (UniqueConstraint('user_id'),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(
        String(16),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

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

    subscription_id = Column(
        String(16),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )
    subscriptions_plan = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    auto_renew = Column(Boolean, nullable=False, server_default=expression.true())
    active = Column(Boolean, nullable=False, server_default=expression.true())

    trial_used = Column(Boolean, nullable=False, server_default=expression.false())
    projects_used = Column(Integer, nullable=False, server_default="0")
    documents_uploaded = Column(Integer, nullable=False, server_default="0")
    queries_made = Column(Integer, nullable=False, server_default="0")
    features_enabled = Column(ARRAY(String), nullable=True)

    user = relationship("User", back_populates="subscription")


# -------------------------
# DOCUMENT TABLE
# -------------------------
class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        String(16),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    storage_key = Column(String, nullable=False)
    url = Column(String, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted = Column(Boolean, nullable=False, server_default=expression.false())

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    user = relationship("User", back_populates="documents")


# -------------------------
# DOCUMENT CHUNK TABLE
# -------------------------
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    vector_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="chunks")
