# from sqlalchemy.ext.asyncio import AsyncSession
# from . import models, schemas
# from .auth import get_password_hash
# from typing import Union
# from app.odoo_services import  create_odoo_user
# from datetime import datetime, timedelta
# import logging
# # from .logging_model import RequestLog
# from sqlalchemy.future import select
# from .models import User
# from sqlalchemy import select
# from .models import Document, DocumentChunk, Subscription
# logger = logging.getLogger(__name__)

# async def create_user(db: AsyncSession, user: Union[schemas.UserCreate, schemas.CreateUserByAdmin], role: str = "customer", user_id: str = None):
#     hashed_password = await get_password_hash(user.password)
#     db_user = models.User(
#         id=user_id, 
#         username=user.username,
#         email=user.email,
#         hashed_password=hashed_password,
#         first_name=user.first_name,
#         last_name=user.last_name,
#         company_name=user.company_name,
#         phone_number=user.phone_number,
#         country=user.country,
#         timezone=user.timezone,
#         subscription_plan=user.subscription_plan,
#         role=role,
#         trial_start_date=datetime.utcnow(),
#         trial_expiry_date=datetime.utcnow() + timedelta(days=5),
#     )
    
#     db.add(db_user)
#     await db.commit()
#     await db.refresh(db_user)
#     return db_user


# # # In crud.py add this function
# # async def create_request_log(db: AsyncSession, log_data: dict):
 
# #     try:
# #         db_log = RequestLog(
# #             timestamp=log_data["timestamp"],
# #             method=log_data["method"],
# #             path=log_data["path"],
# #             ip=log_data["ip"],
# #             status_code=log_data["status_code"],
# #             process_time_ms=log_data["process_time_ms"],
# #             user_agent=log_data["user_agent"],
# #             additional_data=log_data.get("additional_data")
# #         )
# #         db.add(db_log)
# #         await db.commit()
# #         await db.refresh(db_log)
# #         return db_log
# #     except Exception as e:
# #         await db.rollback()
# #         raise e
    
# async def get_user_by_id(db: AsyncSession, user_id: str):
#     result = await db.execute(select(User).where(User.id == user_id))
#     return result.scalars().first()



# # async def create_document(db: AsyncSession, user_id: str, filename: str, content_type: str, size: int, storage_key: str):
# #     doc = Document(user_id=user_id, filename=filename, content_type=content_type, size=size, storage_key=storage_key)
# #     db.add(doc)
# #     await db.commit()
# #     await db.refresh(doc)
# #     return doc
# async def create_document(
#     db: AsyncSession,
#     user_id: str,
#     filename: str,
#     content_type: str,
#     size: int,
#     storage_key: str,
#     url: str = None  # <-- new param
# ):
#     doc = Document(
#         user_id=user_id,
#         filename=filename,
#         content_type=content_type,
#         size=size,
#         storage_key=storage_key,
#         url=url  # <-- store url if provided
#     )
#     db.add(doc)
#     await db.commit()
#     await db.refresh(doc)
#     return doc


# async def create_document_chunk(db: AsyncSession, document_id: int, chunk_index: int, text: str, vector_id: str = None):
#     chunk = DocumentChunk(document_id=document_id, chunk_index=chunk_index, text=text, vector_id=vector_id)
#     db.add(chunk)
#     await db.commit()
#     await db.refresh(chunk)
#     return chunk

# async def get_documents_for_user(db: AsyncSession, user_id: str):
#     res = await db.execute(select(Document).where(Document.user_id == user_id, Document.deleted == False))
#     return res.scalars().all()

# async def mark_document_deleted(db: AsyncSession, document_id: int):
#     doc = await db.get(Document, document_id)
#     if not doc:
#         return None
#     doc.deleted = True
#     await db.commit()
#     return doc

# # subscription counters - note: Subscription.subscription_id == users.id
# async def increment_documents_counter(db: AsyncSession, user_id: str, by: int = 1):
#     sub = await db.get(Subscription, user_id)
#     if not sub:
#         return None
#     sub.documents_uploaded = (sub.documents_uploaded or 0) + by
#     await db.commit()
#     return sub

# async def increment_queries_counter(db: AsyncSession, user_id: str, by: int = 1):
#     sub = await db.get(Subscription, user_id)
#     if not sub:
#         return None
#     sub.queries_made = (sub.queries_made or 0) + by
#     await db.commit()
#     return sub
# async def user_has_documents(db, user_id: int) -> bool:
#     result = await db.execute(
#         select(models.Document).where(models.Document.user_id == user_id)
#     )
#     return result.scalars().first() is not None
from sqlalchemy.ext.asyncio import AsyncSession
from . import models, schemas
from .auth import get_password_hash
from typing import Union
from app.odoo_services import  create_odoo_user
from datetime import datetime, timedelta
import logging
# from .logging_model import RequestLog
from sqlalchemy.future import select
from .models import User
from sqlalchemy import select
from .models import Document, DocumentChunk, Subscription
from app.utils import usage_checker

logger = logging.getLogger(__name__)

async def create_user(db: AsyncSession, user: Union[schemas.UserCreate, schemas.CreateUserByAdmin], role: str = "customer", user_id: str = None):
    hashed_password = await get_password_hash(user.password)
    db_user = models.User(
        id=user_id, 
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        first_name=user.first_name,
        last_name=user.last_name,
        company_name=user.company_name,
        phone_number=user.phone_number,
        country=user.country,
        timezone=user.timezone,
        subscription_plan=user.subscription_plan,
        role=role,
        trial_start_date=datetime.utcnow(),
        trial_expiry_date=datetime.utcnow() + timedelta(days=5),
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_user_by_id(db: AsyncSession, user_id: str):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    return result.scalars().first()

async def create_document(
    db: AsyncSession,
    user_id: str,
    filename: str,
    content_type: str,
    size: int,
    storage_key: str,
    url: str = None
):
    user = await get_user_by_id(db, user_id)
    # Check usage limit
    if await usage_checker.check_usage_limit(user, "documents", db):
        raise Exception("Document upload limit reached for your plan.")
    
    doc = models.Document(
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        size=size,
        storage_key=storage_key,
        url=url
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    # Increment usage counter
    # await increment_documents_counter(db, user_id)
    return doc

async def create_document_chunk(db: AsyncSession, document_id: int, chunk_index: int, text: str, vector_id: str = None):
    chunk = models.DocumentChunk(document_id=document_id, chunk_index=chunk_index, text=text, vector_id=vector_id)
    db.add(chunk)
    await db.commit()
    await db.refresh(chunk)
    return chunk

async def get_documents_for_user(db: AsyncSession, user_id: str):
    res = await db.execute(select(models.Document).where(models.Document.user_id == user_id, models.Document.deleted == False))
    return res.scalars().all()

async def mark_document_deleted(db: AsyncSession, document_id: int):
    doc = await db.get(models.Document, document_id)
    if not doc:
        return None
    doc.deleted = True
    await db.commit()
    return doc

async def increment_documents_counter(db: AsyncSession, user_id: str, by: int = 1):
    sub = await db.get(models.Subscription, user_id)
    if not sub:
        return None
    # Check usage limit before increment (for free users)
    user = await get_user_by_id(db, user_id)
    if await usage_checker.check_usage_limit(user, "documents", db):
        raise Exception("Cannot increment, document limit reached.")
    sub.documents_uploaded = (sub.documents_uploaded or 0) + by
    await db.commit()
    return sub

async def increment_queries_counter(db: AsyncSession, user_id: str, by: int = 1):
    sub = await db.get(models.Subscription, user_id)
    if not sub:
        return None
    user = await get_user_by_id(db, user_id)
    if await usage_checker.check_usage_limit(user, "ai_queries", db):
        raise Exception("Cannot increment, query limit reached.")
    sub.queries_made = (sub.queries_made or 0) + by
    await db.commit()
    return sub

async def user_has_documents(db, user_id: int) -> bool:
    result = await db.execute(
        select(models.Document).where(models.Document.user_id == user_id)
    )
    return result.scalars().first() is not None
