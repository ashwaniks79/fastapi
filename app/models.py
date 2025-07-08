

from sqlalchemy import Column, Integer, String, Boolean, DateTime, TIMESTAMP, text, ARRAY, JSON
from datetime import timezone, timedelta
from sqlalchemy.sql import func
from .database import Base
from sqlalchemy import func
from sqlalchemy.orm import relationship  # Add this import
from sqlalchemy import ForeignKey  # Add this import
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    company_information_page_files = Column(JSON, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())   
    phone_number = Column(String, nullable=False)            
    country = Column(String, nullable=False)                 
    timezone = Column(String, nullable=False)               
    subscription_plan = Column(String, nullable=False, default="free")     
    is_verified = Column(Boolean, default=False)
    role = Column(String, default="customer")
    permissions = Column(ARRAY(String), default=["read"])
    otp_code = Column(String, nullable=True)
    otp_verified = Column(Boolean(create_constraint=True), server_default='false', nullable=False)
    otp_attempts = Column(Integer, default=0)
    otp_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    otp_created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=True)
    # In the User model in models.py, add:
    company_info = relationship("CompanyInformationPageDetails", back_populates="user", uselist=False)
    user_unique_id = Column(String(16), unique=True, nullable=False, index=True)
    access_token = Column(String, nullable=True)

    
class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    company_name = Column(String)
    role = Column(String)
    phone_number = Column(String)
    country = Column(String)
    timezone = Column(String)
    subscription_plan = Column(String, server_default="free")
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    permissions = Column(ARRAY(String), default=["read", "write", "delete"])

# Add this to models.py
class CompanyInformationPageDetails(Base):
    __tablename__ = "company_information_page_details"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
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
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    terms_accepted = Column(Boolean, nullable=False)
    user = relationship("User", back_populates="company_info")