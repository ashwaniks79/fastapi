from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.utils.usage_checker import check_usage_limit
from app.auth import get_current_user

router = APIRouter()

@router.post("/create-project")
async def create_project(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if check_usage_limit(current_user, "projects"):
        raise HTTPException(status_code=403, detail="Project limit reached. Please upgrade your plan.")

    # Create your project logic here...
    current_user.projects_used += 1
    await db.commit()

    return {"message": "Project created successfully"}
