

#import statements all in one 
from app.constants import COUPONS, TIER_FEATURES, TIER_PRICING
from fastapi import Depends, Header, FastAPI, HTTPException, status, Request, BackgroundTasks, Body, File, UploadFile, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.future import select
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import smtplib
import uuid
import logging
import random
from app.database import engine
from app.routes import payment, webhook
import traceback
# from app.odoo_connector import get_odoo_connection
import json
from dotenv import load_dotenv
import io
from sqlalchemy import update  # Add this import
from fastapi import Header
from email.mime.text import MIMEText
from jose import jwt, JWTError
import os
from typing import Union
from sqlalchemy import delete 
from . import database, models, schemas, crud, auth
from .schemas import UserOut
from .auth import get_current_user, get_current_admin, create_access_token, create_refresh_token, verify_password
from .models import User
from .database import get_db
# from app.logging_model import RequestLog
import base64
from datetime import timezone
from typing import List, Optional
from fastapi import UploadFile, File, Form
from pydantic import EmailStr  # Add this import
import secrets
import os
import logging
import boto3
from dotenv import load_dotenv
from app.odoo_services import create_odoo_user
from app.schemas import SubscriptionResponse
import requests
from fastapi import HTTPException
from app.models import Subscription 
from .auth import OTP_EXPIRE_FOR_RESET_MINUTES
from app.schemas import UpgradeSubscriptionRequest, UpgradeSubscriptionResponse
import requests
from fastapi import HTTPException
from app import auth
from app.odoo_routes import router as odoo_router
from fastapi.concurrency import run_in_threadpool
from app.routes import dashboard, projects
from app.routes import files as files_router, chat as chat_router, agent as agent_router
from app.services.storage import upload_file_to_spaces
from app.security import encrypt_password, decrypt_password 

# Load environment variables
load_dotenv()
app = FastAPI()
# main.py
# Include the Odoo test endpoint
app.include_router(odoo_router)
app.include_router(payment.router, prefix="/api")
# app.include_router(webhook.router)
app.include_router(webhook.router, prefix="/payment")
app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(projects.router, tags=["Projects"])
app.include_router(files_router.router, prefix="/api", tags=["Files"])
app.include_router(chat_router.router, prefix="/api", tags=["AI"])
app.include_router(agent_router.router, prefix="/api", tags=["Agent"])

#app start
#logs 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
#file uploads
UPLOAD_DIR = "uploads/company_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

#Mailgun connects
MAILGUN_API_KEY = auth.MAILGUN_API_KEY
MAILGUN_DOMAIN = auth.MAILGUN_DOMAIN
EMAIL_SENDER = auth.EMAIL_SENDER
#file types
COMPANY_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".svg", ".jfif"}  # image/*
REGISTRATION_DOC_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png",".doc",".txt"}
ADDITIONAL_FILES_EXTENSIONS = {".pdf", ".doc", ".docx", ".xlsx", ".jpg", ".jpeg",".png",".txt"}
#allowed files
def allowed_file(filename: str, allowed_extensions: set) -> bool:
    ext = os.path.splitext(filename.lower())[1]
    return ext in allowed_extensions

#app middleware log requests 

logging.basicConfig(
    filename="app.log",  
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
    
#CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://170.64.163.105:3001","https://dashboard.eredoxpro.com"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#  Request logging middleware (DB part removed)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now(timezone.utc)

    if request.url.path in ["/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)

    try:
        response = await call_next(request)
    except HTTPException as http_exc:
        process_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        log_data = {
            "timestamp": start_time.isoformat(),
            "method": request.method,
            "path": request.url.path,
            "ip": request.client.host if request.client else None,
            "status_code": http_exc.status_code,
            "process_time_ms": process_time,
            "user_agent": request.headers.get("user-agent"),
            "error": http_exc.detail
        }
        logger.error(json.dumps(log_data))
        raise http_exc
    except Exception as e:
        process_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        logger.error(f"Request failed: {str(e)}")
        raise

    process_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    log_data = {
        "timestamp": start_time.isoformat(),
        "method": request.method,
        "path": request.url.path,
        "ip": request.client.host if request.client else None,
        "status_code": response.status_code,
        "process_time_ms": process_time,
        "user_agent": request.headers.get("user-agent"),
    }

    # Extra info: login attempts
    if request.url.path == "/login":
        try:
            body = await request.json()
            log_data["additional_data"] = {
                "login_attempt": {
                    "email": body.get("email"),
                    "success": response.status_code == 200
                }
            }
        except Exception as e:
            logger.warning(f"Failed to parse login data: {str(e)}")

    # Extra info: file uploads
    if request.url.path == "/upload":
        try:
            log_data["additional_data"] = {
                "file_upload": True,
                "content_type": request.headers.get("content-type")
            }
        except Exception as e:
            logger.warning(f"Failed to log upload details: {str(e)}")

    logger.info(json.dumps(log_data))
    return response
#start models
# @app.on_event("startup")
# async def on_startup():
#     async with database.engine.begin() as conn:
#         await conn.run_sync(models.Base.metadata.create_all)
#         await conn.run_sync(RequestLog.metadata.create_all)


@app.on_event("startup")
async def on_startup():
    """
    Startup event:
    - Do NOT auto-create tables
    - Always rely on Alembic migrations
    - Only check DB connectivity
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda conn: None)  # just connection test
        print("✅ Database connection successful")
    except Exception as e:
        print("❌ Database connection failed:", e)
        raise
#register API's
@app.post("/register")
async def register(
    user: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # 1) If a verified user already exists -> block
    existing_user = await crud.get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2) If there's an existing pending registration -> tell them to verify/resend
    pending = await crud.get_pending_user_by_email(db, user.email)
    if pending:
        # If existing pending and not expired -> instruct to verify or resend
        if pending.otp_expires_at and datetime.now(timezone.utc) < pending.otp_expires_at:
            raise HTTPException(status_code=400, detail="OTP already sent for this email. Please verify or resend OTP.")
        else:
            # expired pending -> delete and allow new registration
            await crud.delete_pending_user(db, pending)

    # 3) Create pending user record (encrypted password)
    user_id = secrets.token_hex(8)
    otp = str(random.randint(1000, 9999))
    otp_expires = datetime.now(timezone.utc) + timedelta(minutes=int(auth.OTP_EXPIRE_MINUTES))
    password_enc = encrypt_password(user.password)

    pending_data = {
        "id": user_id,
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "company_name": user.company_name,
        "phone_number": user.phone_number,
        "country": user.country,
        "timezone": user.timezone,
        "subscription_plan": user.subscription_plan or "free",
        "password_enc": password_enc,
        "otp_code": otp,
        "otp_expires_at": otp_expires,
        "otp_attempts": 0
    }

    try:
        await crud.create_pending_user(db, pending_data)
    except Exception as e:
        logger.error(f"Failed to create pending user: {e}")
        raise HTTPException(status_code=500, detail="Failed to register. Try again later.")

    # send otp async
    background_tasks.add_task(send_otp_email, user.email, otp)

    return {
        "status": "true",
        "message": "OTP sent. Please verify to complete registration.",
        "email": user.email
    }

###sending welcome email after register


async def send_welcome_email(email: str, first_name: str, user: User, id: str):
    welcome_message = f"""
Subject: 👋 Welcome to EredoxPro – Let’s Set Up Your Business Portal 🚀<br><br>
Hi {first_name}<br><br>
👋 Welcome to EredoxPro — your AI-powered business command centre.<br>
We're excited to have you join our platform! You've taken the first step toward smarter, faster business operations tailored to your industry. 💼✨<br><br>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br><br>
🔧 <strong>What Happens Next?</strong><br><br>
To activate your portal, please complete your Company Setup:<br><br>
👉 <a href="https://dashboard.eredoxpro.com/completeprofile/companyinformationpage?uid={id}">Complete Your Company Setup</a><br><br>
This is where you'll:<br>
•  Describe your business and upload documents<br>
•  Select the Managers (modules) you want to enable<br>
•  Configure your company dashboard for a personalized experience<br><br>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br><br>
🔐 <strong>Your Data. Your Control.</strong><br><br>
At EredoxPro, your data belongs to you — always. 🔒<br><br>
Here's how we keep your portal secure:<br>
•  We do not share, resell, or transmit your data to any third party<br>
•  All business data stays within your company instance<br>
•  When you delete data, it's permanently erased and cannot be recovered<br>
•  You can review our full <a href=https://dashboard.eredoxpro.com/legal/datasecurity">Data Security & Privacy Commitment</a><br><br>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br><br>
📄 <strong>User Acknowledgement & Disclaimer</strong><br><br>
To proceed, please review and accept the following during onboarding:<br>
•  You confirm you are running a legitimate business<br>
•  You agree not to upload any content or file that may:<br>
   ◦  Violate the law<br>
   ◦  Include scams, malicious links, viruses, or trojans<br>
   ◦  Harm the reputation or integrity of Eredox Pty Ltd or its users<br>
•  You understand that deleted data is not recoverable unless re-submitted<br><br>
📄 <a href="https://dashboard.eredoxpro.com/legal/termsofuse">Review our Terms of Use & Legal Policy</a><br><br>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br><br>
💬 <strong>Need Help?</strong><br>
Contact us anytime or simply reply to this email. We're here to support you.<br><br>
Let's get your business running smarter with EredoxPro. ⚙️🤖<br><br>
Warm regards,<br>
<strong>The EredoxPro Team</strong> 👨‍💻👩‍💻
"""

    response = requests.post(
        f"https://api.mailgun.net/v3/{auth.MAILGUN_DOMAIN}/messages",
        auth=("api", auth.MAILGUN_API_KEY),
        data={
            "from": auth.EMAIL_SENDER,
            "to": [email],
            "subject": "Welcome to EredoxPro - Let's Set Up Your Business Portal",
            "html": welcome_message
        },
    )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to send welcome email: {response.text}")

    return {"message": f"Welcome email sent to {first_name}"}

    # msg = MIMEText(welcome_message, 'html')
    # msg["Subject"] = "Welcome to EredoxPro - Let's Set Up Your Business Portal"
    # msg["From"] = auth.EMAIL_SENDER
    # msg["To"] = email
    # try:
    #     with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    #         server.login(auth.EMAIL_SENDER, auth.EMAIL_APP_PASSWORD)
    #         server.sendmail(auth.EMAIL_SENDER, [email], msg.as_string())
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"Failed to send welcome email: {str(e)}")
    # return {"message": f"Welcome email sent to {first_name}"}
##send_otp mail
async def send_otp_email(email: str, otp: str):
    body = f"""Your OTP verification code is: {otp}\nThis code will expire in {auth.OTP_EXPIRE_MINUTES} minutes."""

    response = requests.post(
        f"https://api.mailgun.net/v3/{auth.MAILGUN_DOMAIN}/messages",
        auth=("api", auth.MAILGUN_API_KEY),
        data={
            "from": auth.EMAIL_SENDER,
            "to": [email],
            "subject": "Your OTP Verification Code",
            "text": body
        },
    )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Mailgun error: {response.text}")

    return {"message": f"OTP sent to {email}"}
##verify otp 
@app.post("/verify-otp", response_model=schemas.UnifiedLoginResponse)
async def verify_otp(
    otp_data: schemas.OTPVerify,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None),  # optional
):
    pending = await crud.get_pending_user_by_email(db, otp_data.email)
    if not pending:
        # explicit message as you asked
        raise HTTPException(status_code=404, detail="Your account is not registered or OTP not requested.")

    # attempts check
    if (pending.otp_attempts or 0) + 1 >= int(auth.OTP_ATTEMPTS_LIMIT):
        await crud.delete_pending_user(db, pending)
        raise HTTPException(status_code=400, detail="Email verification attempt exceeded. Please register again.")

    # expiry check
    if pending.otp_expires_at and datetime.now(timezone.utc) > pending.otp_expires_at:
        # expired
        await crud.delete_pending_user(db, pending)
        raise HTTPException(status_code=400, detail="OTP has expired. Please register again.")

    # wrong OTP
    if pending.otp_code != otp_data.otp:
        pending.otp_attempts = (pending.otp_attempts or 0) + 1
        await crud.update_pending_user(db, pending, otp_attempts=pending.otp_attempts)
        attempts_left = int(auth.OTP_ATTEMPTS_LIMIT) - pending.otp_attempts
        raise HTTPException(
            status_code=400,
            detail=f"Invalid OTP. {attempts_left} attempts remaining."
        )

    # ✅ OTP correct -> create real User and related resources
    try:
        plain_password = decrypt_password(pending.password_enc)
    except Exception as e:
        logger.error(f"Failed to decrypt pending password: {e}")
        await crud.delete_pending_user(db, pending)
        raise HTTPException(status_code=500, detail="Internal error while processing registration")

    # Create user via crud.create_user (it will hash the password)
    user_payload = schemas.UserCreate(
        username=pending.username,
        email=pending.email,
        password=plain_password,
        first_name=pending.first_name,
        last_name=pending.last_name,
        company_name=pending.company_name,
        phone_number=pending.phone_number,
        country=pending.country,
        timezone=pending.timezone,
        subscription_plan=pending.subscription_plan or "free",
    )

    try:
        new_user = await crud.create_user(db, user_payload, role="customer", user_id=pending.id)
    except Exception as e:
        logger.error(f"Failed to create user after OTP verification: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user. Try again later.")

    # Odoo sync (only now)
    try:
        odoo_user_data = {
            "first_name": new_user.first_name,
            "last_name": new_user.last_name,
            "email": new_user.email,
            "plain_password": plain_password,
            "plan_type": getattr(new_user, "subscription_plan", "free") or "free"
        }
        partner_id = create_odoo_user(odoo_user_data)
        # If you store partner_id in user
        new_user.partner_id = partner_id
    except Exception as e:
        logger.error(f"[Odoo Sync] Failed: {e}")

    # Create subscription (same logic as before)
    subscription_features = {
        "free": ['Access to 3 Basic Agents', 'Limited Usage of Tools'],
        "silver": ['Access to All Standard Agents', 'Limited Media/Marketing Tools'],
        "gold": ['Full Access to 50+ Agents', 'Includes Document, Vision, Marketing Tools']
    }
    features = subscription_features.get(new_user.subscription_plan.lower(), [])
    new_subscription = Subscription(
        subscription_id=new_user.id,
        subscriptions_plan=new_user.subscription_plan,
        features_enabled=features
    )
    db.add(new_subscription)

    # Generate tokens and attach
    access_token = auth.create_access_token(data={"sub": new_user.email, "role": new_user.role})
    refresh_token = auth.create_refresh_token(data={"sub": new_user.email, "role": new_user.role})
    new_user.access_token = access_token

    # Final commit (user update, subscription, partner_id, access_token)
    await db.commit()
    await db.refresh(new_user)

    # Remove pending record now that real user exists
    await crud.delete_pending_user(db, pending)

    # Send welcome email in background
    background_tasks.add_task(send_welcome_email, new_user.email, new_user.first_name, new_user, new_user.id)

    # Return unified login response so client can use tokens
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "status": "true",
        "role": new_user.role,
        "message": "Registration successful and OTP verified.",
        "user": schemas.UserOut.model_validate(new_user, from_attributes=True)
    }


# ---------------------------
# RESEND OTP: operate on pending
# ---------------------------
@app.post("/resend-otp")
async def resend_otp(
    background_tasks: BackgroundTasks,
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    # If a verified user exists -> don't resend
    existing_user = await crud.get_user_by_email(db, email)
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists. Please login.")

    pending = await crud.get_pending_user_by_email(db, email)
    if not pending:
        raise HTTPException(status_code=404, detail="No pending registration found. Please register first.")

    if pending.otp_attempts >= int(auth.OTP_ATTEMPTS_LIMIT):
        # too many attempts -> delete pending and force re-register
        await crud.delete_pending_user(db, pending)
        raise HTTPException(status_code=400, detail="Too many attempts. Please register again.")

    # regenerate otp & reset attempts & extend expiry
    otp = str(random.randint(1000, 9999))
    otp_expires = datetime.now(timezone.utc) + timedelta(minutes=int(auth.OTP_EXPIRE_MINUTES))
    await crud.update_pending_user(db, pending, otp_code=otp, otp_attempts=0, otp_expires_at=otp_expires)

    background_tasks.add_task(send_otp_email, email, otp)
    return {"otp_verified": False, "otp_attempts": 0, "message": "OTP resent."}

@app.post("/login", response_model=schemas.UnifiedLoginResponse)
async def unified_login(
    background_tasks: BackgroundTasks,
    data: schemas.LoginRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    # 🔹 Admin login
    result = await db.execute(
        select(User).where(User.email == data.email, User.role == "admin")
    )
    admin_user = result.scalar_one_or_none()
    if admin_user and await verify_password(data.password, admin_user.hashed_password):
        access_token = create_access_token(data={"sub": admin_user.email, "role": "admin"})
        refresh_token = create_refresh_token(data={"sub": admin_user.email, "role": "admin"})  
        admin_user.access_token = access_token
        await db.commit()
        await db.refresh(admin_user)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,  
            "token_type": "bearer",
            "status": "true",
            "role": "admin",
            "message": "Login successful as admin",
            "user": schemas.UserOut.model_validate(admin_user, from_attributes=True)
        }

    # 🔹 Normal user login
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    # Pehle user exist karta hai ya nahi check karo
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # OTP verification enforce karo
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify OTP before logging in.")

    # Password validate karo
    if not await verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Tokens generate karo
    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.email, "role": user.role})  
    user.access_token = access_token
    await db.commit()
    await db.refresh(user)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,  
        "token_type": "bearer",
        "status": "true",
        "role": user.role,
        "message": f"Login successful as {user.role}",
        "user": schemas.UserOut.model_validate(user, from_attributes=True)
    }

####refresh token
@app.post("/refresh-token")
async def refresh_token(
    background_tasks: BackgroundTasks,
    request: Request
):
    data = await request.json()
    token = data.get("refresh_token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing refresh token")
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        if payload.get("scope") != "refresh_token":
            raise HTTPException(status_code=401, detail="Invalid scope for token")
        email = payload.get("sub")
        role = payload.get("role")
        if not email or not role:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        new_access_token = create_access_token(data={"sub": email, "role": role})
        # Example: background_tasks.add_task(log_token_refresh, email)
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
####user profile
@app.get("/users/me/read", response_model=schemas.UserOut)
async def read_customer(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    # Example: background_tasks.add_task(audit_read_user, current_user.email)
    return current_user
##logout
@app.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    background_tasks: BackgroundTasks,
    token: str = Depends(auth.oauth2_scheme)
):
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email = payload.get("sub")
        role = payload.get("role")
        if not email or not role:
            raise HTTPException(status_code=401, detail="Invalid token")
        # Example: background_tasks.add_task(log_logout, email)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {
        "message": f"Logout successful for role '{role}' and user '{email}'. Thankyou!"
    }
###create user admin can create staff and contractors
@app.post("/admin/create-user", response_model=schemas.UserOut)
async def create_user_by_admin(
    user_data: schemas.CreateUserByAdmin,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    if user_data.role not in ["staff", "contractor"]:
        raise HTTPException(status_code=400, detail="Admins can only create staff or contractor accounts")
    existing_user = await auth.get_user_by_email_from_users_table(db, user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    # Example: background_tasks.add_task(audit_admin_create_user, current_admin.email, user_data.email)
    return await crud.create_user(db, user=user_data, role=user_data.role,  user_id=secrets.token_hex(8)
)
#####admin can get all users staff, contractors and customers 
@app.get("/admin/users", response_model=List[schemas.UserOut])
async def get_all_users(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(database.get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    result = await db.execute(select(models.User).where(models.User.role != "admin"))
    users = result.scalars().all()
    # Example: background_tasks.add_task(audit_admin_read_users, current_admin.email)
    return users
#######admin can update customer, staff and contractor
@app.put("/user/update/{user_id}", response_model=schemas.UserOut)
async def update_any_user(
    user_id: str,
    user_update: schemas.UnifiedUserUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.User = Depends(get_current_admin)
):
    result = await db.execute(select(models.User).filter(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    # Example: background_tasks.add_task(audit_user_update, current_user.email, user_id)
    return user
#####admin can delete customer, staff and contractor
@app.delete("/user/delete/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(database.get_db),
    current_user=Depends(get_current_admin)
):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    # Example: background_tasks.add_task(audit_user_delete, current_user.email, user_id)
    print(f"User with ID {user_id} deleted successfully.")
    return JSONResponse(content={"message": "User deleted successfully"}, status_code=200)
#########we can get company name by user_id
@app.get("/user/company_name/{user_id}", tags=["User"])
async def get_company_name_by_unique_id(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Admin does not have a company name.")
    if not user.otp_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please complete OTP verification first."
        )
    return {"company_name": user.company_name}


@app.post("/user/company_information_page", response_model=schemas.CompanyInformationResponse)
async def create_company_information(
    user_id: str = Form(...),
    business_reg_number: str = Form(...),
    industry_type: str = Form(...),
    other_industry: Optional[str] = Form(None),
    num_employees: Optional[int] = Form(None),
    company_website: Optional[str] = Form(None),
    business_phone: str = Form(...),
    business_email: schemas.EmailStr = Form(...),
    address_street: str = Form(...),
    address_city: str = Form(...),
    address_state: str = Form(...),
    address_postcode: str = Form(...),
    address_country: str = Form(...),
    terms_accepted: bool = Form(...),
    company_logo: Optional[UploadFile] = File(None),
    registration_doc: Optional[UploadFile] = File(None),  # 👈optional for update
    additional_files: Optional[List[UploadFile]] = File(None),
    db: AsyncSession = Depends(get_db)
):
    try:
        # --- user check ---
        result = await db.execute(select(models.User).where(models.User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.role == "admin":
            return {"detail": "Admin does not require company information page"}

        if not user.otp_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email with OTP before submitting company information"
            )

        if not terms_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must accept the terms and conditions"
            )

        # --- check if already submitted ---
        existing_info_result = await db.execute(
            select(models.CompanyInformationPageDetails).where(
                models.CompanyInformationPageDetails.user_id == user.id
            )
        )
        existing_info = existing_info_result.scalar_one_or_none()

        os.makedirs(UPLOAD_DIR, exist_ok=True)

        # 🖼️ company logo
        company_logo_url = None
        if company_logo:
            if not allowed_file(company_logo.filename, COMPANY_LOGO_EXTENSIONS):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Company logo file type is not supported"
                )
            logo_filename = f"logo_{user.id}_{company_logo.filename}"
            company_logo_url = await upload_file_to_spaces(
                file_obj=await company_logo.read(),
                filename=logo_filename,
                content_type=company_logo.content_type
            )

        # 📄 registration doc
        registration_doc_url = None
        if registration_doc: 
            if not allowed_file(registration_doc.filename, REGISTRATION_DOC_EXTENSIONS):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Registration document file type is not supported"
                )
            regdoc_filename = f"regdoc_{user.id}_{registration_doc.filename}"
            registration_doc_url = await upload_file_to_spaces(
                file_obj=await registration_doc.read(),
                filename=regdoc_filename,
                content_type=registration_doc.content_type
            )

        # 📎 additional files
        additional_files_urls = []
        if additional_files:
            for file in additional_files:
                if not allowed_file(file.filename, ADDITIONAL_FILES_EXTENSIONS):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Additional file '{file.filename}' type is not supported"
                    )
                additional_filename = f"additional_{user.id}_{file.filename}"
                url = await upload_file_to_spaces(
                    file_obj=await file.read(),
                    filename=additional_filename,
                    content_type=file.content_type
                )
                additional_files_urls.append(url)

        if existing_info:
            # 🔄 Update logic
            existing_info.company_name = user.company_name or existing_info.company_name
            existing_info.business_reg_number = business_reg_number
            existing_info.industry_type = industry_type
            existing_info.other_industry = other_industry
            existing_info.num_employees = num_employees
            existing_info.company_website = company_website
            existing_info.business_phone = business_phone
            existing_info.business_email = business_email
            existing_info.address_street = address_street
            existing_info.address_city = address_city
            existing_info.address_state = address_state
            existing_info.address_postcode = address_postcode
            existing_info.address_country = address_country
            existing_info.terms_accepted = terms_accepted

            # if company_logo_url:
            #     existing_info.company_logo_path = company_logo_url
            # if registration_doc_url:
            #     existing_info.registration_doc_path = registration_doc_url
            # if additional_files_urls:
            #     existing_info.additional_files_paths = additional_files_urls
            if company_logo_url is not None:
                existing_info.company_logo_path = company_logo_url or existing_info.company_logo_path

            # Registration doc only update if new file is uploaded
            if registration_doc_url is not None:
                existing_info.registration_doc_path = registration_doc_url or existing_info.registration_doc_path

            # Additional files: decide append vs replace
            if additional_files_urls is not None and len(additional_files_urls) > 0:
                # If you want to REPLACE
                existing_info.additional_files_paths = additional_files_urls

            await db.commit()
            await db.refresh(existing_info)

            return {
                "detail": "Company information updated successfully",
                **schemas.CompanyInformationResponse.from_orm(existing_info).dict()
            }

        else:
            # 🆕 Create new entry
            if not registration_doc_url:
                raise HTTPException(
                    status_code=400,
                    detail="Registration document is required for new submission"
                )

            company_info = models.CompanyInformationPageDetails(
                user_id=user.id,
                company_name=user.company_name,
                business_reg_number=business_reg_number,
                industry_type=industry_type,
                other_industry=other_industry,
                num_employees=num_employees,
                company_website=company_website,
                business_phone=business_phone,
                business_email=business_email,
                address_street=address_street,
                address_city=address_city,
                address_state=address_state,
                address_postcode=address_postcode,
                address_country=address_country,
                terms_accepted=terms_accepted,
                company_logo_path=company_logo_url,
                registration_doc_path=registration_doc_url,
                additional_files_paths=additional_files_urls
            )

            db.add(company_info)
            await db.commit()
            await db.refresh(company_info)

            return {
                "detail": "Company information submitted successfully",
                **schemas.CompanyInformationResponse.from_orm(company_info).dict()
            }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        traceback.print_exc()
        print(f"Internal Server Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/user/company_information_page", response_model=schemas.CompanyInformationResponse)
async def get_company_information(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]

    try:
        payload = auth.decode_access_token(token)
        user_email = payload.get("sub")
        if user_email is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # get user
    result = await db.execute(select(models.User).where(models.User.email == user_email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Admin check
    if user.role == "admin":
        return {"detail": "Admin does not require company information page"}

    # fetch company info
    company_result = await db.execute(
        select(models.CompanyInformationPageDetails).where(
            models.CompanyInformationPageDetails.user_id == user.id
        )
    )
    company_info = company_result.scalar_one_or_none()

    if not company_info:
        # New user, no data
        return {"detail": "No company information submitted yet"}

    # Return existing info (prefill)
    return schemas.CompanyInformationResponse.from_orm(company_info)


########check user filled company information page
@app.get("/check-company-info-status", response_model=dict)
async def check_company_info_status(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]

    try:
        payload = auth.decode_access_token(token)
        user_email = payload.get("sub")
        if user_email is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(models.User).where(models.User.email == user_email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        return {"filled": True, "message": "Admin does not require company information submission"}
    company_result = await db.execute(
        select(models.CompanyInformationPageDetails).where(models.CompanyInformationPageDetails.user_id == user.id)
    )
    company_info = company_result.scalar_one_or_none()

    if company_info:
        return {"filled": True, "message": "Company information already submitted"}
    else:
        return {"filled": False, "message": "Company information not submitted yet"}
#############user can delete account of a particular use

@app.delete("/delete-account", status_code=status.HTTP_200_OK)
async def delete_account(
    credentials: schemas.DeleteAccountRequest,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # ✅ Only allow self-deletion
    if current_user.email != credentials.email:
        raise HTTPException(status_code=403, detail="You can only delete your own account")

    # ✅ Fetch the user to delete
    result = await db.execute(select(models.User).where(models.User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ✅ Verify password
    if not await auth.verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")

    # ✅ Delete related company information
    await db.execute(
        delete(models.CompanyInformationPageDetails)
        .where(models.CompanyInformationPageDetails.user_id == user.id)
    )

    # ✅ Delete the user
    await db.delete(user)
    await db.commit()

    return {"detail": f"Account associated with {credentials.email} has been deleted."}
##########email schema
class EmailSchema(BaseModel):
    email: EmailStr
###############password reset sending otp
@app.post("/password-reset/send-otp")
async def send_password_reset_otp(  # 🔄 changed from send_otp
    background_tasks: BackgroundTasks,
    data: EmailSchema = Body(...),
    db: AsyncSession = Depends(get_db)
):
    email = data.email
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp_code = str(random.randint(100000, 999999))
    user.otp_code = otp_code
    user.otp_attempts = 0
    user.otp_verified = False
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=auth.OTP_EXPIRE_FOR_RESET_MINUTES)
    await db.commit()

    background_tasks.add_task(send_password_reset_otp_email, user.email, otp_code)  # 🔄 changed function name

    return {"message": "OTP sent to your email"}
###########mail function for reset password

async def send_password_reset_otp_email(email: str, otp_code: str):
    html_content = f"""
Hi,<br><br>

Your OTP for password reset is: <b>{otp_code}</b><br><br>

This OTP will expire in {auth.OTP_EXPIRE_FOR_RESET_MINUTES} minutes.<br><br>

If you did not request this, please ignore this email.<br><br>

Thank you,<br>
EredoxPro Team
"""
    response = requests.post(
        f"https://api.mailgun.net/v3/{auth.MAILGUN_DOMAIN}/messages",
        auth=("api", auth.MAILGUN_API_KEY),
        data={
            "from": auth.EMAIL_SENDER,
            "to": [email],
            "subject": "Your OTP for Password Reset",
            "html": html_content
        },
    )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Mailgun error: {response.text}")
    
    return {"message": f"Password reset OTP sent to {email}"}

### 2a. Endpoint to verify OTP ###
@app.post("/password-reset/verify-otp")
async def verify_otp(
    email: str = Body(...),
    otp: str = Body(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.otp_code != otp:
        user.otp_attempts = (user.otp_attempts or 0) + 1
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if datetime.now(timezone.utc) > user.otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP expired")

    user.otp_verified = True
    await db.commit()

    return {"message": "OTP verified successfully"}


### 2b. Endpoint to reset password ###
@app.post("/password-reset/reset-password")
async def reset_password(
    background_tasks: BackgroundTasks,
    email: str = Body(...),
    new_password: str = Body(...),
    confirm_password: str = Body(...),
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    payload = auth.decode_access_token(authorization.removeprefix("Bearer ").strip())
    if payload.get("sub") != email:
        raise HTTPException(status_code=403, detail="Token does not match email")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.otp_verified:
        raise HTTPException(status_code=400, detail="OTP not verified")

    # Password validations
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if len(new_password) < 7 or not any(c.isupper() for c in new_password):
        raise HTTPException(status_code=400, detail="Password must be at least 7 characters and include an uppercase letter")

    # Hash new password and update user
    hashed = await auth.get_password_hash(new_password)
    user.hashed_password = hashed

    # Clear OTP data
    user.otp_code = None
    user.otp_verified = False
    user.otp_expires_at = None
    user.otp_attempts = 0
    await db.commit()

    background_tasks.add_task(send_password_reset_success_email, user.email, user.first_name)

    return {"message": "Password reset successful and confirmation email sent"}

########reset password success email
async def send_password_reset_success_email(email: str, first_name: str):
    html_content = f"""
Hi {first_name},<br><br>

✅ Your password has been successfully reset.<br><br>

If you did not request this, please contact our support team immediately.<br><br>

Thank you,<br>
EredoxPro Team
"""
    response = requests.post(
        f"https://api.mailgun.net/v3/{auth.MAILGUN_DOMAIN}/messages",
        auth=("api", auth.MAILGUN_API_KEY),
        data={
            "from": auth.EMAIL_SENDER,
            "to": [email],
            "subject": "✅ Password Reset Confirmation",
            "html": html_content
        },
    )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Mailgun error: {response.text}")
    
    return {"message": f"Password reset confirmation email sent to {email}"}

@app.post("/forget-password")
async def send_password_link_email(
    background_tasks: BackgroundTasks,
    data: EmailSchema = Body(...),
    db: AsyncSession = Depends(get_db)
):
    email = data.email
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Use static frontend reset page + user_id
    reset_link = f"https://dashboard.eredoxpro.com/forget-password?uid={user.id}"
    background_tasks.add_task(send_forget_password_link_email, user.email, user.first_name, reset_link)

    return {"message": f"Password reset link sent to {email}"}

#################send email for forget password##############################
async def send_forget_password_link_email(email: str, first_name: str, reset_link: str):
    html_content = f"""
Hi {first_name},<br><br>
We received a request to reset your password.<br><br>
👉 <a href="{reset_link}">Click here to reset your password</a><br><br>
If you did not request this, please ignore this email.<br><br>
Thanks,<br>
EredoxPro Team
"""

    response = requests.post(
        f"https://api.mailgun.net/v3/{auth.MAILGUN_DOMAIN}/messages",
        auth=("api", auth.MAILGUN_API_KEY),
        data={
            "from": auth.EMAIL_SENDER,
            "to": [email],
            "subject": "🔐 Reset Your Password - EredoxPro",
            "html": html_content
        },
    )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Mailgun error: {response.text}")
    
    return {"message": f"Password reset link sent to {email}"}

@app.post("/forget-password/set-new-password")
async def set_password_via_link(
    user_id: str = Body(...),
    new_password: str = Body(...),
    confirm_password: str = Body(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    if len(new_password) < 7 or not any(c.isupper() for c in new_password):
        raise HTTPException(status_code=400, detail="Password must be at least 7 characters and include an uppercase letter")

    hashed = await auth.get_password_hash(new_password)
    user.hashed_password = hashed
    await db.commit()

    return {"message": "Your password has been successfully updated"}

#########logs to show in request log###########################

async def log_admin_access(email: str):
    """Log admin access to sensitive company information"""
    logger.info(f"Admin {email} accessed all company information")

async def log_user_access(email: str):
    """Log user access to their own company information"""
    logger.info(f"User {email} accessed their company information")


##############unified login to check company information for admin and user####################
@app.get("/company-information", response_model=Union[List[schemas.CompanyInformationResponse], schemas.CompanyInformationResponse])
async def get_company_information(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user:  models.User = Depends(auth.get_current_user)
):
    """
    Unified endpoint that returns:
    - All company info if admin (using get_current_user which verifies role)
    - Only the user's info if regular user
    """
    try:
        admin = await auth.get_current_admin(current_user)
        # Admin branch  
        result = await db.execute(
            select(models.CompanyInformationPageDetails)
            .where(models.CompanyInformationPageDetails.user_id != admin.id)
            )
        company_info = result.scalars().all()
        background_tasks.add_task(log_admin_access, admin.email)
        return company_info
    except HTTPException as admin_exc:
        if admin_exc.status_code == 403:
            # User branch (since admin check failed)
            result = await db.execute(
                select(models.CompanyInformationPageDetails)
                .where(models.CompanyInformationPageDetails.user_id == current_user.id)
            )
            company_info = result.scalar_one_or_none()
            if not company_info:
                raise HTTPException(
                    status_code=404,
                    detail="Company information not found. Please complete your company profile."
                )
            background_tasks.add_task(log_user_access, current_user.email)
            return company_info
        raise admin_exc

@app.put("/user/company_information_files/edit", response_model=schemas.CompanyInformationResponse)
async def edit_company_information_files(
    user_id: str = Form(...),
    company_logo: Optional[UploadFile] = File(None),
    registration_doc: Optional[UploadFile] = File(None),
    additional_files: Optional[List[UploadFile]] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # ✅ If not admin, force user_id to their own ID
    # if current_user.role != "admin":
    #     user_id = current_user.id
    if current_user.role != "admin":
        if user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="You are not authorized to edit another user's information.")


    # ✅ Fetch the target user (admin might be editing someone else)
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ✅ Fetch company info linked to the user
    result = await db.execute(
        select(models.CompanyInformationPageDetails).where(models.CompanyInformationPageDetails.user_id == user.id)
    )
    company_info = result.scalar_one_or_none()
    if not company_info:
        raise HTTPException(status_code=404, detail="Company information not found")

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # ✅ Upload company logo
    if company_logo:
        if not allowed_file(company_logo.filename, COMPANY_LOGO_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail="Invalid logo file type. Allowed: PNG, JPG, JPEG, GIF, BMP, TIFF, SVG, JFIF"
            )
        logo_filename = f"logo_{user.id}_{company_logo.filename}"
        logo_url = await upload_file_to_spaces(
            file_obj=await company_logo.read(),
            filename=logo_filename,
            content_type=company_logo.content_type
        )
        company_info.company_logo_path = logo_url

    # ✅ Upload registration doc
    if registration_doc:
        if not allowed_file(registration_doc.filename, REGISTRATION_DOC_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail="Invalid registration document. Allowed: PDF, JPG, JPEG, PNG"
            )
        regdoc_filename = f"regdoc_{user.id}_{registration_doc.filename}"
        regdoc_url =await upload_file_to_spaces(
            file_obj=await registration_doc.read(),
            filename=regdoc_filename,
            content_type=registration_doc.content_type
        )
        company_info.registration_doc_path = regdoc_url

    # ✅ Upload additional files
    additional_files_urls = []
    if additional_files:
        for file in additional_files:
            if not allowed_file(file.filename, ADDITIONAL_FILES_EXTENSIONS):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid additional file '{file.filename}'. Allowed: PDF, DOC, DOCX, XLSX, JPG, JPEG"
                )
            additional_filename = f"additional_{user.id}_{file.filename}"
            url = await upload_file_to_spaces(
                file_obj=await file.read(),
                filename=additional_filename,
                content_type=file.content_type
            )
            additional_files_urls.append(url)
        company_info.additional_files_paths = additional_files_urls

    # ✅ Save updates
    await db.commit()
    await db.refresh(company_info)

    return company_info
############Delete API of docs#############################

@app.delete("/user/company_information_files/delete_docs", status_code=204)
async def delete_company_information_docs(
    user_id: str = Form(...),
    delete_logo: Optional[bool] = Form(False),
    delete_registration_doc: Optional[bool] = Form(False),
    delete_additional_files: Optional[bool] = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 🔐 Restrict to self or admin
    if current_user.role != "admin" and user_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to delete this user's files.")
    
    # 🧍‍♂️ Fetch the user
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 🏢 Fetch company info
    result = await db.execute(
        select(models.CompanyInformationPageDetails).where(models.CompanyInformationPageDetails.user_id == user_id)
    )
    company_info = result.scalar_one_or_none()
    if not company_info:
        raise HTTPException(status_code=404, detail="Company information not found")

    # 🚮 Delete logo
    if delete_logo and company_info.company_logo_path:
        # Optional: call delete_file_from_spaces(company_info.company_logo_path)
        company_info.company_logo_path = None

    # 🚫 Prevent deletion of registration_doc_path (it is mandatory)
    if delete_registration_doc:
        raise HTTPException(status_code=400, detail="Registration document cannot be deleted.")


    # 🚮 Delete additional files
    if delete_additional_files and company_info.additional_files_paths:
        # Optional: loop through and delete each from cloud
        company_info.additional_files_paths = []

    # 💾 Save changes
    await db.commit()
    return
#############Get subscription########################

@app.get("/subscription/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    result = await db.execute(
        select(models.Subscription).where(models.Subscription.subscription_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return subscription
#################Get upgrade API##########################

@app.post("/manage/subscriptions", response_model=UpgradeSubscriptionResponse)
async def upgrade_subscription(
    request: UpgradeSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    tier = request.tier.lower()

    if tier not in TIER_PRICING:
        raise HTTPException(status_code=400, detail="Invalid subscription tier.")

    base_price = TIER_PRICING[tier]
    discount = 0.0
    coupon_applied = None

    # Apply coupon if provided and valid
    if request.coupon_code:
        code = request.coupon_code.upper()
        if code in COUPONS:
            discount = COUPONS[code]
            coupon_applied = f"{int(discount * 100)}% discount applied"
        else:
            raise HTTPException(status_code=400, detail="Invalid coupon code.")

    amount_to_charge = round(base_price * (1 - discount), 2)

    # Simulate billing success
    billing_successful = True
    if not billing_successful:
        raise HTTPException(status_code=500, detail="Billing failed. Try again later.")

    # Only update existing subscription
    result = await db.execute(
        select(models.Subscription).where(models.Subscription.subscription_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription record not found for this user.")
    if subscription.subscriptions_plan == tier:
        raise HTTPException(status_code=400, detail=f"You are already subscribed to the {tier.capitalize()} plan.")

    # Update subscription fields
    subscription.subscriptions_plan = tier
    subscription.features_enabled = TIER_FEATURES[tier]
    subscription.active = True
    subscription.end_date = None

    await db.commit()
    await db.refresh(subscription)

    return UpgradeSubscriptionResponse(
        success=True,
        message=f"Subscription upgraded to {tier.capitalize()} successfully.",
        plan=tier,
        amount_charged=amount_to_charge,
        coupon_applied=coupon_applied
    )
#############Cancel plan#######################
@app.post("/subscription/cancel")
async def cancel_subscription(
    user_id: str = Query(None, description="User ID to cancel subscription for (admin only)"),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # ✅ Admin: can cancel anyone's subscription (or their own if no user_id is passed)
    # ✅ User: can only cancel their own subscription
    if current_user.role == "admin":
        target_user_id = user_id or str(current_user.id)
    else:
        if user_id and user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to cancel this subscription.")
        target_user_id = str(current_user.id)

    # 🔍 Fetch the subscription for the target user
    result = await db.execute(
        select(models.Subscription).where(models.Subscription.subscription_id == target_user_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found for this user.")

    # ❌ Cancel the subscription and downgrade to 'free'
    subscription.active = False
    subscription.end_date = datetime.utcnow()
    subscription.subscriptions_plan = "free"
    subscription.features_enabled = TIER_FEATURES["free"]

    # 🔄 Update the user's subscription_plan as well
    result = await db.execute(
        select(models.User).where(models.User.id == target_user_id)
    )
    user = result.scalar_one_or_none()
    if user:
        user.subscription_plan = "free"

    await db.commit()
    return {
    "message": "Subscription cancelled successfully. Your plan has been downgraded to Free.",
    "new_plan": "free",
    "features_enabled": TIER_FEATURES["free"]
}

# @app.get("/odoo/test")
# async def test_odoo():
#     try:
#         odoo = get_odoo_connection()
#         partners = odoo.env['res.partner'].search_read([], ['name', 'email'], limit=5)
#         return {"partners": partners}
#     except Exception as e:
#         return {"error": str(e)}
# @app.post("/subscription/cancel", status_code=204)
# async def cancel_subscription(
#     user_id: str,  # The user whose subscription to cancel
#     db: AsyncSession = Depends(get_db),
#     current_user: models.User = Depends(auth.get_current_user)
# ):
#     # Admin can cancel any subscription (including their own)
#     # User can cancel only their own subscription
#     if current_user.role != "admin" and user_id != str(current_user.id):
#         raise HTTPException(status_code=403, detail="Not authorized to cancel this subscription.")

#     # Fetch subscription for the user_id
#     result = await db.execute(select(models.Subscription).where(models.Subscription.subscription_id == user_id))
#     subscription = result.scalar_one_or_none()

#     if not subscription:
#         raise HTTPException(status_code=404, detail="Subscription not found for this user.")

#     # Cancel subscription: set active to False and end_date to now
#     subscription.active = False
#     subscription.end_date = datetime.utcnow()
#     subscription.subscriptions_plan = "free"
#     subscription.features_enabled = []

#     # Also update user's subscription_plan field
#     result = await db.execute(select(models.User).where(models.User.id == user_id))
#     user = result.scalar_one_or_none()
#     if user:
#         user.subscription_plan = "free"

#     await db.commit()

#     return  # 204 No Content