

from sqlalchemy import Column, Integer, String, Boolean, DateTime, TIMESTAMP, text, ARRAY, JSON
from datetime import timezone, timedelta
from sqlalchemy.sql import func
from .database import Base
from sqlalchemy import func

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
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

