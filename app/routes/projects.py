# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.ext.asyncio import AsyncSession
# from app import models
# from app.database import get_db
# from app.auth import get_current_user
# from app.utils.usage_checker import check_usage_limit

# router = APIRouter()

# @router.post("/create-project")
# async def create_project(
#     db: AsyncSession = Depends(get_db),
#     current_user: models.User = Depends(get_current_user)
# ):
#     # Fetch subscription by user_id
#     sub = await db.get(models.Subscription, current_user.id)
#     if not sub:
#         raise HTTPException(status_code=400, detail="Subscription missing")

#     # Check usage limit using Subscription instance
#     if await check_usage_limit(sub, "projects"):
#         raise HTTPException(status_code=403, detail="Project limit reached. Please upgrade your plan.")

#     # Increment project usage
#     sub.projects_used = (sub.projects_used or 0) + 1
#     await db.commit()

#     return {"message": "Project created successfully"}
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app import models
from app.database import get_db
from app.auth import get_current_user
from app.utils.usage_checker import check_usage_limit

router = APIRouter()

@router.post("/create-project")
async def create_project(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    sub = await db.get(models.Subscription, current_user.id)
    if not sub:
        raise HTTPException(status_code=400, detail="Subscription missing")

    if await check_usage_limit(current_user, "projects", db):
        raise HTTPException(status_code=403, detail="Project limit reached. Please upgrade your plan.")

    sub.projects_used = (sub.projects_used or 0) + 1
    await db.commit()

    return {"message": "Project created successfully"}
