# app/routes/files.py
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app import crud, models
from app.services.storage import upload_bytes, generate_presigned_url, delete_object
from app.services.embeddings import process_document_embeddings
from app.utils.usage_checker import check_usage_limit
import uuid
import os
from pathlib import Path

router = APIRouter(prefix="/files", tags=["files"])

# Allowed by content-type
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/json",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "image/svg+xml",
    "image/jfif",
    "image/avif",
}

# Allowed by extension (fallback)
ALLOWED_EXTS = {
    ".pdf", ".txt", ".md", ".json", ".csv",
    ".docx", ".xlsx",
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".svg", ".jfif", ".avif"
}

MAX_SIZE = 30 * 1024 * 1024  # 30 MB
PUBLIC_BUCKET = os.getenv("SPACES_PUBLIC", "false").lower() == "true"


def _is_allowed(file: UploadFile) -> bool:
    ctype_ok = (file.content_type in ALLOWED_CONTENT_TYPES)
    ext_ok = (Path(file.filename or "").suffix.lower() in ALLOWED_EXTS)
    return ctype_ok or ext_ok

@router.post("/upload")
async def upload_user_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if await check_usage_limit(current_user, "documents", db):
        raise HTTPException(status_code=403, detail="Document upload limit reached. Please upgrade your plan or subscription to continue.")

    if not _is_allowed(file):
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large.")

    key = f"{current_user.id}/{uuid.uuid4().hex}_{file.filename}"
    acl_setting = "public-read" if PUBLIC_BUCKET else "private"

    upload_result = await upload_bytes(key, content, file.content_type, acl=acl_setting)
    storage_key = upload_result.get("key") if isinstance(upload_result, dict) else key
    direct_url = upload_result.get("url") if isinstance(upload_result, dict) else None

    # Save document (no URL stored to avoid migrations)
    doc = await crud.create_document(
        db,
        user_id=current_user.id,
        filename=file.filename,
        content_type=file.content_type,
        size=len(content),
        storage_key=storage_key
        # url not stored
    )
    await crud.increment_documents_counter(db, current_user.id, by=1)

    # background embedding (works for images too if OCR available)
    background_tasks.add_task(process_document_embeddings, doc.id)

    # Return a viewable URL
    view_url = direct_url
    if not PUBLIC_BUCKET:
        view_url = await generate_presigned_url(storage_key, expires_in=3600)

    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "url": view_url
    }

@router.get("/")
async def list_files(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    docs = await crud.get_documents_for_user(db, current_user.id)
    out = []
    for d in docs:
        if PUBLIC_BUCKET:
            # construct a quick direct URL using storage convention
            # NOTE: if you changed public URL pattern, reflect it in storage._build_public_url
            region = os.getenv("SPACES_REGION")
            bucket = os.getenv("SPACES_BUCKET")
            file_url = f"https://{bucket}.{region}.digitaloceanspaces.com/{d.storage_key}"
        else:
            file_url = await generate_presigned_url(d.storage_key, expires_in=3600)

        out.append({
            "id": d.id,
            "filename": d.filename,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
            "url": file_url
        })
    return out

@router.get("/{document_id}/view")
async def view_file(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    doc = await db.get(models.Document, document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")

    # If public bucket → build static URL
    if PUBLIC_BUCKET:
        region = os.getenv("SPACES_REGION")
        bucket = os.getenv("SPACES_BUCKET")
        file_url = f"https://{bucket}.{region}.digitaloceanspaces.com/{doc.storage_key}"
    else:
        # Generate a *fresh* presigned URL every time
        file_url = await generate_presigned_url(doc.storage_key, expires_in=300)  # 5 mins

    return {"url": file_url}


@router.delete("/{document_id}")
async def delete_file(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    doc = await db.get(models.Document, document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")

    await delete_object(doc.storage_key)
    await crud.mark_document_deleted(db, document_id)

    from app.services.vector_db import delete_vectors_by_document
    await delete_vectors_by_document(document_id)

    await crud.increment_documents_counter(db, current_user.id, by=-1)
    return {"message": "deleted"}