


from fastapi import Depends, Header, FastAPI, HTTPException, status, Request, BackgroundTasks, Body, File, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.future import select
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import smtplib
import logging
import random
import json
from sqlalchemy import update  # Add this import
from fastapi import Header
from email.mime.text import MIMEText
from jose import jwt, JWTError
import os
from sqlalchemy import delete 
from . import database, models, schemas, crud, auth
from .schemas import UserOut
from .auth import get_current_user, get_current_admin, create_access_token, create_refresh_token, verify_password
from .models import User, Admin
from .database import get_db
from app.logging_model import RequestLog
import base64
from datetime import timezone
from typing import List, Optional
from fastapi import UploadFile, File, Form
from pydantic import EmailStr  # Add this import
import secrets
from .auth import OTP_EXPIRE_FOR_RESET_MINUTES
app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads/company_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".svg"
}

def allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_EXTENSIONS

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://170.64.163.105:3001"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now(ZoneInfo("Australia/Sydney"))
    if request.url.path in ["/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)
    try:
        response = await call_next(request)
    except HTTPException as http_exc:
        process_time = (datetime.now(ZoneInfo("Australia/Sydney")) - start_time).total_seconds() * 1000
        log_data = {
            "timestamp": start_time.astimezone(timezone.utc).replace(tzinfo=None),
            "method": request.method,
            "path": request.url.path,
            "ip": request.client.host if request.client else None,
            "status_code": http_exc.status_code,
            "process_time_ms": process_time,
            "user_agent": request.headers.get("user-agent"),
            "error": http_exc.detail
        }
        logger.error(json.dumps({**log_data, "timestamp": log_data["timestamp"].isoformat()}))
        raise http_exc
    except Exception as e:
        process_time = (datetime.now(ZoneInfo("Australia/Sydney"))- start_time).total_seconds() * 1000
        logger.error(f"Request failed: {str(e)}")
        raise
    process_time = (datetime.now(ZoneInfo("Australia/Sydney")) - start_time).total_seconds() * 1000
    log_data = {
        "timestamp": start_time.astimezone(timezone.utc).replace(tzinfo=None),
        "method": request.method,
        "path": request.url.path,
        "ip": request.client.host if request.client else None,
        "status_code": response.status_code,
        "process_time_ms": process_time,
        "user_agent": request.headers.get("user-agent"),
    }
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
    if request.url.path == "/upload":
        try:
            log_data["additional_data"] = {
                "file_upload": True,
                "content_type": request.headers.get("content-type")
            }
        except Exception as e:
            logger.warning(f"Failed to log upload details: {str(e)}")
    console_log = {**log_data, "timestamp": log_data["timestamp"].isoformat()}
    logger.info(json.dumps(console_log, default=str))
    try:
        db = database.async_session()
        await crud.create_request_log(db, log_data)
    except Exception as e:
        logger.error(f"Database log failed: {str(e)}")
    finally:
        await db.close()
    return response

@app.on_event("startup")
async def on_startup():
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
        from .logging_model import RequestLog
        await conn.run_sync(RequestLog.metadata.create_all)

@app.post("/register", response_model=schemas.UnifiedLoginResponse)
async def register(
    user: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(database.get_db)
):
    existing_user = await auth.get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    # 🔐 Generate 16-character unique ID
    def generate_unique_id(length=16):
        return secrets.token_hex(length // 2).upper()

    user_unique_id = generate_unique_id()

    new_user = await crud.create_user(db, user, role="customer", user_unique_id=user_unique_id)
    otp = str(random.randint(1000, 9999))
    otp_expires = datetime.now(ZoneInfo("Australia/Sydney")) + timedelta(minutes=int(auth.OTP_EXPIRE_MINUTES))
    new_user.otp_code = otp
    new_user.otp_verified = False
    new_user.otp_attempts = 0
    new_user.otp_expires_at = otp_expires
    
    await db.commit()
    await db.refresh(new_user)
    background_tasks.add_task(send_otp_email, new_user.email, otp)
    access_token = auth.create_access_token(data={"sub": new_user.email, "role": new_user.role})
    refresh_token = auth.create_refresh_token(data={"sub": new_user.email, "role": new_user.role})
    new_user.access_token = access_token
    await db.commit()
    await db.refresh(new_user)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "status": "true",
        "role": new_user.role,
        "message": "Registration successful. OTP sent.",
        "user": schemas.UserOut.model_validate(new_user, from_attributes=True)
    }

async def send_welcome_email(email: str, first_name: str, user: User, user_unique_id: str):
    welcome_message = f"""

Subject: 👋 Welcome to EredoxPro – Let’s Set Up Your Business Portal 🚀<br><br>
Hi {first_name}<br><br>
👋 Welcome to EredoxPro — your AI-powered business command centre.<br>
We're excited to have you join our platform! You've taken the first step toward smarter, faster business operations tailored to your industry. 💼✨<br><br>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br><br>
🔧 <strong>What Happens Next?</strong><br><br>
To activate your portal, please complete your Company Setup:<br><br>

👉 <a href="http://localhost:3000/completeprofile/companyinformationpage?uid={user_unique_id}">Complete Your Company Setup</a><br><br>


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
•  You can review our full <a href="http://localhost:3000/legal/datasecurity">Data Security & Privacy Commitment</a><br><br>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br><br>
📄 <strong>User Acknowledgement & Disclaimer</strong><br><br>
To proceed, please review and accept the following during onboarding:<br>
•  You confirm you are running a legitimate business<br>
•  You agree not to upload any content or file that may:<br>
   ◦  Violate the law<br>
   ◦  Include scams, malicious links, viruses, or trojans<br>
   ◦  Harm the reputation or integrity of Eredox Pty Ltd or its users<br>
•  You understand that deleted data is not recoverable unless re-submitted<br><br>
📄 <a href="http://localhost:3000/legal/termsofuse">Review our Terms of Use & Legal Policy</a><br><br>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br><br>
💬 <strong>Need Help?</strong><br>
Contact us anytime or simply reply to this email. We're here to support you.<br><br>
Let's get your business running smarter with EredoxPro. ⚙️🤖<br><br>
Warm regards,<br>
<strong>The EredoxPro Team</strong> 👨‍💻👩‍💻
"""

    
    msg = MIMEText(welcome_message, 'html')
    msg["Subject"] = "Welcome to EredoxPro - Let's Set Up Your Business Portal"
    msg["From"] = auth.EMAIL_SENDER
    msg["To"] = email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(auth.EMAIL_SENDER, auth.EMAIL_APP_PASSWORD)
            server.sendmail(auth.EMAIL_SENDER, [email], msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send welcome email: {str(e)}")
    return {"message": f"Welcome email sent to {first_name}"}

async def send_otp_email(email: str, otp: str):
    msg = MIMEText(f"""Your OTP verification code is: {otp}
This code will expire in {auth.OTP_EXPIRE_MINUTES} minutes.
If you didn't request this, please ignore this email.""")
    msg["Subject"] = "Your OTP Verification Code"
    msg["From"] = auth.EMAIL_SENDER
    msg["To"] = email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(auth.EMAIL_SENDER, auth.EMAIL_APP_PASSWORD)
            server.sendmail(auth.EMAIL_SENDER, [email], msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP email: {str(e)}")
    return {"message": f"OTP sent to {email}"}



@app.post("/verify-otp", response_model=schemas.OTPResponse)
async def verify_otp(
    otp_data: schemas.OTPVerify,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(...),
):
    
    result = await db.execute(select(models.User).where(models.User.email == otp_data.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.otp_verified:
        raise HTTPException(status_code=400, detail="OTP already verified")
    if user.otp_attempts + 1 >= auth.OTP_ATTEMPTS_LIMIT:
        await db.delete(user)
        await db.commit()
        raise HTTPException(status_code=400, detail="Email verification attempt exceeded. Please register again.")
    if user.otp_expires_at and datetime.now(ZoneInfo("Australia/Sydney")) > user.otp_expires_at.astimezone(ZoneInfo("Australia/Sydney")):
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new OTP.")
    if user.otp_code != otp_data.otp:
        user.otp_attempts += 1
        await db.commit()
        await db.refresh(user)
        attempts_left = auth.OTP_ATTEMPTS_LIMIT - user.otp_attempts
        raise HTTPException(
            status_code=400,
            detail=f"Invalid OTP. {attempts_left} attempts remaining."
        )
    # user.otp_verified = True
    # user.otp_code = None
    # user.is_verified = True
    await db.execute(update(User)
        .where(User.email == otp_data.email)
            .values(otp_verified=True, is_verified=True))

    await db.commit()
    await db.refresh(user)
    # saved_token = user.access_token
    # Example: background_tasks.add_task(some_audit_log, user.email, "otp_verified")
    # background_tasks.add_task(send_welcome_email, user.email, user.first_name)
    background_tasks.add_task(send_welcome_email, user.email, user.first_name, user.id, user.user_unique_id)
    return {"otp_verified": True, "otp_attempts": user.otp_attempts, "message": f"Welcome email sent to {user.first_name}"}
    # return {"otp_verified": True, "otp_attempts": user.otp_attempts}

@app.post("/resend-otp", response_model=schemas.OTPResponse)
async def resend_otp(
    background_tasks: BackgroundTasks,
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(models.User).where(models.User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.otp_verified:
        raise HTTPException(status_code=400, detail="OTP already verified")
    if user.otp_attempts >= auth.OTP_ATTEMPTS_LIMIT:
        wait_time = auth.OTP_EXPIRE_MINUTES
        raise HTTPException(
            status_code=400,
            detail=f"Too many attempts. Please wait {wait_time} minutes before requesting a new OTP."
        )
    otp = str(random.randint(1000, 9999))  
    otp_expires = datetime.now(ZoneInfo("Australia/Sydney")) + timedelta(minutes=int(auth.OTP_EXPIRE_MINUTES))
    user.otp_code = otp
    user.otp_attempts = 0
    user.otp_expires_at = otp_expires
    await db.commit()
    await db.refresh(user)
    background_tasks.add_task(send_otp_email, user.email, otp)
    return {"otp_verified": user.otp_verified, "otp_attempts": user.otp_attempts}



@app.post("/login", response_model=schemas.UnifiedLoginResponse)
async def unified_login(
    background_tasks: BackgroundTasks,
    data: schemas.LoginRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Admin).where(Admin.email == data.email))
    admin_user = result.scalar_one_or_none()
    if admin_user and await verify_password(data.password, admin_user.hashed_password):
        access_token = create_access_token(data={"sub": admin_user.email, "role": "admin"})
        refresh_token = create_refresh_token(data={"sub": admin_user.email, "role": "admin"})  
        # Example: background_tasks.add_task(log_login_attempt, admin_user.email, True)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,  
            "token_type": "bearer",
            "status": "true",
            "role": "admin",
            "message": "Login successful as admin",
            "user": schemas.AdminOut.model_validate(admin_user, from_attributes=True)
        }
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    # if not user or not await verify_password(data.password, user.hashed_password):
    #     # Example: background_tasks.add_task(log_login_attempt, data.email, False)
    #     raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user or not await verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials or email not verified")
    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.email, "role": user.role})  
    # Example: background_tasks.add_task(log_login_attempt, user.email, True)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,  
        "token_type": "bearer",
        "status": "true",
        "role": user.role,
        "message": f"Login successful as {user.role}",
        "user": schemas.UserOut.model_validate(user, from_attributes=True)
    }

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

@app.get("/users/me/read", response_model=schemas.UserOut)
async def read_customer(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    # Example: background_tasks.add_task(audit_read_user, current_user.email)
    return current_user

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

@app.post("/admin/create-user", response_model=schemas.UserOut)
async def create_user_by_admin(
    user_data: schemas.CreateUserByAdmin,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    if user_data.role not in ["staff", "contractor"]:
        raise HTTPException(status_code=400, detail="Admins can only create staff or contractor accounts")
    existing_user = await auth.get_user_by_email_from_users_table(db, user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    # Example: background_tasks.add_task(audit_admin_create_user, current_admin.email, user_data.email)
    return await crud.create_user(db, user=user_data, role=user_data.role)

@app.get("/admin/users", response_model=List[schemas.UserOut])
async def get_all_users(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(database.get_db),
    current_admin: models.Admin = Depends(auth.get_current_admin)
):
    result = await db.execute(select(models.User))
    users = result.scalars().all()
    # Example: background_tasks.add_task(audit_admin_read_users, current_admin.email)
    return users

@app.put("/user/update/{user_id}", response_model=schemas.UserOut)
async def update_any_user(
    user_id: int,
    user_update: schemas.UnifiedUserUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.Admin = Depends(get_current_admin)
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

@app.delete("/user/delete/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
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

@app.get("/user/company_name/{user_unique_id}", tags=["User"])
async def get_company_name_by_unique_id(
    user_unique_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(models.User).where(models.User.user_unique_id == user_unique_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.otp_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please complete OTP verification first."
        )
    return {"company_name": user.company_name}

@app.post("/user/company_information_page", response_model=schemas.CompanyInformationResponse)
async def create_company_information(
    user_unique_id: str = Form(...),  # ✅ NEW: Accept user_unique_id as input
    business_reg_number: str = Form(...),
    industry_type: str = Form(...),
    other_industry: Optional[str] = Form(None),
    num_employees: Optional[int] = Form(None),
    company_website: Optional[str] = Form(None),
    business_phone: str = Form(...),
    business_email: EmailStr = Form(...),
    address_street: str = Form(...),
    address_city: str = Form(...),
    address_state: str = Form(...),
    address_postcode: str = Form(...),
    address_country: str = Form(...),
    terms_accepted: bool = Form(...),
    company_logo: Optional[UploadFile] = File(None),
    registration_doc: UploadFile = File(...),
    additional_files: Optional[List[UploadFile]] = File(None),
    db: AsyncSession = Depends(get_db)
):
    # ✅ NEW: Fetch user from user_unique_id
    result = await db.execute(select(models.User).where(models.User.user_unique_id == user_unique_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.otp_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email with OTP before submitting company information"
        )

    # Validate terms acceptance
    if not terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the terms and conditions"
        )

    # Check if user already has company info
    existing_info = await db.execute(
        select(models.CompanyInformationPageDetails)
        .where(models.CompanyInformationPageDetails.user_id == user.id)
    )
    if existing_info.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company information already submitted"
        )

    # Process file uploads
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Save company logo if provided
    company_logo_path = None
    if company_logo:
        if not allowed_file(company_logo.filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company logo must be an image file (PNG, JPG, JPEG, GIF, BMP, TIFF, SVG)"
            )
        company_logo_filename = f"logo_{user.id}_{company_logo.filename}"
        company_logo_path = os.path.join(UPLOAD_DIR, company_logo_filename)
        with open(company_logo_path, "wb") as buffer:
            buffer.write(await company_logo.read())

    # Save registration document
    if not allowed_file(registration_doc.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration document must be PDF or image file"
        )
    registration_doc_filename = f"regdoc_{user.id}_{registration_doc.filename}"
    registration_doc_path = os.path.join(UPLOAD_DIR, registration_doc_filename)
    with open(registration_doc_path, "wb") as buffer:
        buffer.write(await registration_doc.read())

    # Save additional files if provided
    additional_files_paths = []
    if additional_files:
        for file in additional_files:
            if not allowed_file(file.filename):
                continue  # Skip invalid files
            file_filename = f"additional_{user.id}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, file_filename)
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())
            additional_files_paths.append(file_path)

    # ✅ Use company_name from the user fetched by unique_id
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
        company_logo_path=company_logo_path,
        registration_doc_path=registration_doc_path,
        additional_files_paths=additional_files_paths
    )

    db.add(company_info)
    await db.commit()
    await db.refresh(company_info)

    return company_info

# @app.get("/user/company_name", tags=["User"])
# async def get_company_name(
#     current_user: models.User = Depends(get_current_user),
# ):
#     if not current_user.otp_verified:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Email not verified. Please complete OTP verification first."
#         )
#     return {"company_name": current_user.company_name}

# @app.post("/user/company_information_page", response_model=schemas.CompanyInformationResponse)
# async def create_company_information(
#     company_name: str = Depends(lambda current_user=Depends(get_current_user): current_user.company_name),
#     business_reg_number: str = Form(...),
#     industry_type: str = Form(...),
#     other_industry: Optional[str] = Form(None),
#     num_employees: Optional[int] = Form(None),
#     company_website: Optional[str] = Form(None),
#     business_phone: str = Form(...),
#     business_email: EmailStr = Form(...),
#     address_street: str = Form(...),
#     address_city: str = Form(...),
#     address_state: str = Form(...),
#     address_postcode: str = Form(...),
#     address_country: str = Form(...),
#     terms_accepted: bool = Form(...),
#     company_logo: Optional[UploadFile] = File(None),
#     registration_doc: UploadFile = File(...),
#     additional_files: Optional[List[UploadFile]] = File(None),
#     db: AsyncSession = Depends(get_db),
#     current_user: models.User = Depends(get_current_user)
# ):
#     if not current_user.otp_verified:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Please verify your email with OTP before submitting company information"
#         )
#     # Validate terms acceptance
#     if not terms_accepted:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="You must accept the terms and conditions"
#         )
    

#     # Check if user already has company info
#     existing_info = await db.execute(
#         select(models.CompanyInformationPageDetails)
#         .where(models.CompanyInformationPageDetails.user_id == current_user.id)
#     )
#     if existing_info.scalar_one_or_none():
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Company information already submitted"
#         )

#     # Process file uploads
#     os.makedirs(UPLOAD_DIR, exist_ok=True)
    
#     # Save company logo if provided
#     company_logo_path = None
#     if company_logo:
#         if not allowed_file(company_logo.filename):
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Company logo must be an image file (PNG, JPG, JPEG, GIF, BMP, TIFF, SVG)"
#             )
#         company_logo_filename = f"logo_{current_user.id}_{company_logo.filename}"
#         company_logo_path = os.path.join(UPLOAD_DIR, company_logo_filename)
#         with open(company_logo_path, "wb") as buffer:
#             buffer.write(await company_logo.read())

#     # Save registration document
#     if not allowed_file(registration_doc.filename):
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Registration document must be PDF or image file"
#         )
#     registration_doc_filename = f"regdoc_{current_user.id}_{registration_doc.filename}"
#     registration_doc_path = os.path.join(UPLOAD_DIR, registration_doc_filename)
#     with open(registration_doc_path, "wb") as buffer:
#         buffer.write(await registration_doc.read())

#     # Save additional files if provided
#     additional_files_paths = []
#     if additional_files:
#         for file in additional_files:
#             if not allowed_file(file.filename):
#                 continue  # Skip invalid files
#             file_filename = f"additional_{current_user.id}_{file.filename}"
#             file_path = os.path.join(UPLOAD_DIR, file_filename)
#             with open(file_path, "wb") as buffer:
#                 buffer.write(await file.read())
#             additional_files_paths.append(file_path)

#     # Create company info record - ADDED terms_accepted HERE
#     company_info = models.CompanyInformationPageDetails(
#         user_id=current_user.id,
#         company_name=company_name,
#         business_reg_number=business_reg_number,
#         industry_type=industry_type,
#         other_industry=other_industry,
#         num_employees=num_employees,
#         company_website=company_website,
#         business_phone=business_phone,
#         business_email=business_email,
#         address_street=address_street,
#         address_city=address_city,
#         address_state=address_state,
#         address_postcode=address_postcode,
#         address_country=address_country,
#         terms_accepted=terms_accepted,  # THIS IS THE CRITICAL ADDITION
#         company_logo_path=company_logo_path,
#         registration_doc_path=registration_doc_path,
#         additional_files_paths=additional_files_paths
#     )

#     db.add(company_info)
#     await db.commit()
#     await db.refresh(company_info)

#     return company_info

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

    company_result = await db.execute(
        select(models.CompanyInformationPageDetails).where(models.CompanyInformationPageDetails.user_id == user.id)
    )
    company_info = company_result.scalar_one_or_none()

    if company_info:
        return {"filled": True, "message": "Company information already submitted"}
    else:
        return {"filled": False, "message": "Company information not submitted yet"}

@app.delete("/delete-account", status_code=status.HTTP_200_OK)
async def delete_account(
       credentials: schemas.DeleteAccountRequest,
       db: AsyncSession = Depends(database.get_db)
   ):
       # 1. Fetch user by email
       result = await db.execute(select(models.User).where(models.User.email == credentials.email))
       user = result.scalar_one_or_none()

       if not user:
           raise HTTPException(status_code=404, detail="User  not found")

       # 2. Verify password
       if not await auth.verify_password(credentials.password, user.hashed_password):
           raise HTTPException(status_code=401, detail="Incorrect password")

       # 3. Delete related company information
       await db.execute(delete(models.CompanyInformationPageDetails).where(models.CompanyInformationPageDetails.user_id == user.id))

       # 4. Delete user
       await db.delete(user)
       await db.commit()

       return {"detail": f"Account associated with {credentials.email} has been deleted."}

class EmailSchema(BaseModel):
    email: EmailStr

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
    user.otp_expires_at = datetime.now(ZoneInfo("Australia/Sydney")) + timedelta(minutes=auth.OTP_EXPIRE_FOR_RESET_MINUTES)
    await db.commit()

    background_tasks.add_task(send_password_reset_otp_email, user.email, otp_code)  # 🔄 changed function name

    return {"message": "OTP sent to your email"}


async def send_password_reset_otp_email(email: str, otp_code: str):  # 🔄 changed from send_otp_email
    msg = MIMEText(f"""
Hi,

Your OTP for password reset is: <b>{otp_code}</b>

This OTP will expire in {OTP_EXPIRE_FOR_RESET_MINUTES} minutes.

If you did not request this, please ignore this email.

Thank you,<br>
EredoxPro Team
""", 'html')
    msg["Subject"] = "Your OTP for Password Reset"
    msg["From"] = auth.EMAIL_SENDER
    msg["To"] = email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(auth.EMAIL_SENDER, auth.EMAIL_APP_PASSWORD)
            server.sendmail(auth.EMAIL_SENDER, [email], msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP email: {str(e)}")


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
    if datetime.now(ZoneInfo("Australia/Sydney")) > user.otp_expires_at:
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


async def send_password_reset_success_email(email: str, first_name: str):  # 🔄 changed from send_password_reset_confirmation
    msg = MIMEText(f"""
Hi {first_name},

✅ Your password has been successfully reset.

If you did not request this, please contact our support team immediately.

Thank you,<br>
EredoxPro Team
""", 'html')
    msg["Subject"] = "✅ Password Reset Confirmation"
    msg["From"] = auth.EMAIL_SENDER
    msg["To"] = email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(auth.EMAIL_SENDER, auth.EMAIL_APP_PASSWORD)
            server.sendmail(auth.EMAIL_SENDER, [email], msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send confirmation email: {str(e)}")

# class EmailSchema(BaseModel):
#     email: EmailStr

# @app.post("/password-reset/send-otp")
# async def send_otp(
#     background_tasks: BackgroundTasks,
#     data: EmailSchema = Body(...),
#     db: AsyncSession = Depends(get_db)
# ):
#     email = data.email
#     result = await db.execute(select(User).where(User.email == email))
#     user = result.scalar_one_or_none()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     otp_code = str(random.randint(100000, 999999))
#     user.otp_code = otp_code
#     user.otp_attempts = 0
#     user.otp_verified = False
#     user.otp_expires_at = datetime.now(ZoneInfo("Australia/Sydney")) + timedelta(minutes=auth.OTP_EXPIRE_MINUTES)
#     await db.commit()

#     background_tasks.add_task(send_otp_email, user.email, otp_code)

#     return {"message": "OTP sent to your email"}


# async def send_otp_email(email: str, otp_code: str):
#     msg = MIMEText(f"""
# Hi,

# Your OTP for password reset is: <b>{otp_code}</b>

# This OTP will expire in {auth.OTP_EXPIRE_MINUTES} minutes.

# If you did not request this, please ignore this email.

# Thank you,<br>
# EredoxPro Team
# """, 'html')
#     msg["Subject"] = "Your OTP for Password Reset"
#     msg["From"] = auth.EMAIL_SENDER
#     msg["To"] = email
#     try:
#         with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
#             server.login(auth.EMAIL_SENDER, auth.EMAIL_APP_PASSWORD)
#             server.sendmail(auth.EMAIL_SENDER, [email], msg.as_string())
#     except Exception as e:
#         # Log this in real app, here just raise HTTPException
#         raise HTTPException(status_code=500, detail=f"Failed to send OTP email: {str(e)}")


# ### 2. Endpoint to verify OTP and reset password ###
# @app.post("/password-reset/verify-otp-reset")
# async def verify_otp_and_reset_password(
#     background_tasks: BackgroundTasks,
#     email: str = Body(...),
#     otp: str = Body(...),
#     new_password: str = Body(...),
#     confirm_password: str = Body(...),
#     authorization: str = Header(...),
#     db: AsyncSession = Depends(get_db)
# ):
#     payload = auth.decode_access_token(authorization.removeprefix("Bearer ").strip())
#     if payload.get("sub") != email:
#         raise HTTPException(status_code=403, detail="Token does not match email")
    
#     result = await db.execute(select(User).where(User.email == email))
#     user = result.scalar_one_or_none()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     # Verify OTP
#     if user.otp_code != otp:
#         user.otp_attempts = (user.otp_attempts or 0) + 1
#         await db.commit()
#         raise HTTPException(status_code=400, detail="Invalid OTP")
#     if datetime.now(ZoneInfo("Australia/Sydney")) > user.otp_expires_at:
#         raise HTTPException(status_code=400, detail="OTP expired")

#     # Password validations
#     if new_password != confirm_password:
#         raise HTTPException(status_code=400, detail="Passwords do not match")
#     if len(new_password) < 7 or not any(c.isupper() for c in new_password):
#         raise HTTPException(status_code=400, detail="Password must be at least 7 characters and include an uppercase letter")

#     # Hash new password and update user
#     hashed = await auth.get_password_hash(new_password)
#     user.hashed_password = hashed

#     # Clear OTP data
#     user.otp_code = None
#     user.otp_verified = False
#     user.otp_expires_at = None
#     user.otp_attempts = 0
#     await db.commit()

#     background_tasks.add_task(send_password_reset_confirmation, user.email, user.first_name)

#     return {"message": "Password reset successful and confirmation email sent"}


# async def send_password_reset_confirmation(email: str, first_name: str):
#     msg = MIMEText(f"""
# Hi {first_name},

# ✅ Your password has been successfully reset.

# If you did not request this, please contact our support team immediately.

# Thank you,<br>
# EredoxPro Team
# """, 'html')
#     msg["Subject"] = "✅ Password Reset Confirmation"
#     msg["From"] = auth.EMAIL_SENDER
#     msg["To"] = email
#     try:
#         with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
#             server.login(auth.EMAIL_SENDER, auth.EMAIL_APP_PASSWORD)
#             server.sendmail(auth.EMAIL_SENDER, [email], msg.as_string())
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to send confirmation email: {str(e)}")
