

from pydantic import BaseModel, EmailStr, Field, validator, constr, StringConstraints
from typing import Optional
from typing import Literal, Union
from .models import User  
from typing import Union, TYPE_CHECKING
from typing import Annotated
from datetime import datetime 
from typing import List
import re


class UserCreate(BaseModel):
    first_name: constr(min_length=4)
    last_name: constr(min_length=4)
    username: constr(min_length=4)
    email: EmailStr
    password: constr(min_length=7)
    company_name: constr(min_length=2)
    phone_number: str
    country: constr(min_length=3)
    timezone: constr(min_length=2)
    subscription_plan: constr(min_length=4) = "free"

    @validator("password")
    def password_must_have_uppercase(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Password must include a capital letter")
        return v
    
    @validator("phone_number")
    def validate_phone_number(cls, v):
        if len(v) < 7:
            raise ValueError("Phone number must be greater than 7 digits ")
        if not re.fullmatch(r'^\+?\d{1,3}\d{7,15}$', v):
            raise ValueError("Phone number must be +[country code][7-15 digits] (e.g. +11234567890)")
        return v

class UserOut(BaseModel):
    id: str 
    first_name: str
    last_name: str
    username: str
    email: EmailStr
    company_name: str
    phone_number: str
    country: str
    timezone: str     
    subscription_plan: str = "free"     
    role: str = "customer"
    permissions: list[str] = ["read"]
    otp_verified: bool = False  
    otp_attempts: int = 0  
    


    class Config:
        orm_mode = True

class OTPResponse(BaseModel):
    otp_verified: bool
    otp_attempts: int

class Token(BaseModel):
    access_token: str
    token_type: str
    status: str
    role: Optional[str] = None

class TokenData(BaseModel):
    email: Optional[str] = None

# class AdminOut(BaseModel):
#     id: str
#     first_name: str
#     last_name: str
#     username: str
#     email: EmailStr
#     company_name: str
#     phone_number: str
#     country: str
#     timezone: str
#     subscription_plan: str = "free"
#     role: str = "admin"
#     permissions: list[str] = ["read", "write", "delete"]


#     class Config:
#         orm_mode = True


if TYPE_CHECKING:
    from app.schemas import UserOut, AdminOut, StaffOut, ContractorOut

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @validator("password")
    def validate_password_complexity(cls, v):
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v

    @validator("email")
    def validate_email_format(cls, v):
        if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError("Invalid email address")
        return v

class UnifiedLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    status: str = "true"
    role: str
    message: Optional[str]
    user: UserOut 

    class Config:
        orm_mode = True

UnifiedLoginResponse.update_forward_refs()


class CreateUserByAdmin(BaseModel):
    role: Literal["staff", "contractor"]
    username: constr(min_length=4)
    email: EmailStr
    password: constr(min_length=7)
    first_name: constr(min_length=4)
    last_name: constr(min_length=4)
    company_name: constr(min_length=2)
    phone_number: str
    country: constr(min_length=3)
    timezone: constr(min_length=2)
    subscription_plan: constr(min_length=4) = "free"

    @validator("password")
    def password_must_have_uppercase(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Password must include a capital letter")
        return v
    
    @validator("phone_number")
    def validate_phone_number(cls, v):
        if len(v) < 7:
            raise ValueError("Phone number must be greater than 7 digits ")
        if not re.fullmatch(r'^\+?\d{1,3}\d{7,15}$', v):
            raise ValueError("Phone number must be +[country code][7-15 digits] (e.g. +11234567890)")
        return v

class UnifiedUserUpdate(BaseModel):
    id: Optional[str] = None  # Added ID field for frontend compatibility
    first_name: Optional[constr(min_length=4)] = None
    last_name: Optional[constr(min_length=4)] = None
    username: Optional[constr(min_length=4)] = None
    email: Optional[EmailStr] = None
    company_name: Optional[constr(min_length=2)] = None
    phone_number: Optional[str] = None
    country: Optional[constr(min_length=3)] = None
    timezone: Optional[constr(min_length=2)] = None
    subscription_plan: Optional[constr(min_length=4)] = None

    @validator("phone_number")
    def validate_phone_number(cls, v):
        if v is None:
            return v
        if len(v) < 7:
            raise ValueError("Phone number must be at least 7 digits")
        if not re.fullmatch(r'^\+?\d{1,3}\d{7,15}$', v):
            raise ValueError("Phone number must be +[country code][7-15 digits] (e.g. +11234567890)")
        return v  
    
# Add this to schemas.py
class RequestLogSchema(BaseModel):
    timestamp: datetime
    method: str
    path: str
    ip: Optional[str]
    status_code: int
    process_time_ms: float
    user_agent: Optional[str]
    additional_data: Optional[dict]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
# Add these new schemas
class OTPCreate(BaseModel):
    email: EmailStr
    otp: str

class OTPVerify(BaseModel):
    email: EmailStr
    otp: str

class FileData(BaseModel):
    filename: str
    content_type: str
    saved_path: str
    content_base64: str

class CompanyInfoResponse(BaseModel):
    company_name: str
    uploaded_files: List[FileData]


##########company information page########################

class CompanyInformationBase(BaseModel):
    company_name: str
    business_reg_number: str
    industry_type: str
    other_industry: Optional[str] = None
    num_employees: Optional[int] = None
    company_website: Optional[str] = None
    business_phone: str
    business_email: EmailStr
    address_street: str
    address_city: str
    address_state: str
    address_postcode: str
    address_country: str
    terms_accepted: bool

    @validator('company_website')
    def validate_website(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('Website must start with http:// or https://')
        return v

class CompanyInformationCreate(CompanyInformationBase):
    pass

class CompanyInformationResponse(CompanyInformationBase):
    id: int
    user_id: str
    company_logo_path: Optional[str] = None
    # terms_accepted: bool
    registration_doc_path: str
    additional_files_paths: Optional[List[str]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # class Config:
    #     orm_mode = True
    class Config:
        from_attributes = True
####################################Delete Account#############


class DeleteAccountRequest(BaseModel):
    email: EmailStr
    password: str

################Subscription Schema####################
class SubscriptionResponse(BaseModel):
    subscription_id: str
    subscriptions_plan: str
    start_date: datetime
    end_date: Optional[datetime]
    auto_renew: bool
    active: bool
    features_enabled: List[str]

    class Config:
        orm_mode = True
#################Upgrade and Price Subscription##############


class UpgradeSubscriptionRequest(BaseModel):
    tier: str  # "free", "silver", "gold"
    user_id: str
    success_url: str
    cancel_url: str
    customer_email: EmailStr
    coupon_code: Optional[str] = None
    
class UpgradeSubscriptionResponse(BaseModel):
    success: bool
    message: str
    plan: str
    amount_charged: float
    coupon_applied: Optional[str] = None