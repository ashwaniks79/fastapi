# from datetime import datetime
# from app.constants import USAGE_LIMITS

# def is_trial_expired(user):
#     if user.subscription_plan != "free":
#         return False
#     if not user.trial_expiry_date:
#         return False
#     return datetime.utcnow() > user.trial_expiry_date

# def check_usage_limit(user, usage_type):
#     limits = USAGE_LIMITS.get(user.subscription_plan, {})
#     used = getattr(user, f"{usage_type}_used", 0)
#     allowed = limits.get(usage_type)
#     if allowed is None:
#         return False
#     return used >= allowed

# def usage_summary(user):
#     limits = USAGE_LIMITS.get(user.subscription_plan, {})
#     return {
#         "projects": (user.projects_used, limits.get("projects")),
#         "documents": (user.documents_uploaded, limits.get("documents")),
#         "ai_queries": (user.ai_queries_made, limits.get("ai_queries")),
#         "trial_expired": is_trial_expired(user)
#     }
from datetime import datetime
from app.constants import USAGE_LIMITS
from app import models
from sqlalchemy.ext.asyncio import AsyncSession

def is_trial_expired(user: models.User):
    if user.subscription_plan != "free":
        return False
    if not user.trial_expiry_date:
        return False
    return datetime.utcnow() > user.trial_expiry_date

# canonical map
USAGE_FIELD_MAP = {
    "projects": "projects_used",
    "documents": "documents_uploaded",
    "ai_queries": "queries_made"
}

async def check_usage_limit(user: models.User, usage_type: str, db: AsyncSession) -> bool:
    limits = USAGE_LIMITS.get(user.subscription_plan, {})
    field = USAGE_FIELD_MAP.get(usage_type)
    if not field:
        # invalid usage_type, treat as no limit
        return False

    sub = await db.get(models.Subscription, user.id)
    if not sub:
        # if no subscription found, treat as no limit or deny? Here deny
        return True

    used = getattr(sub, field, 0) or 0
    allowed = limits.get(usage_type)

    if allowed is None:
        # no limit set means no limit enforcement
        return False

    return used >= allowed

async def usage_summary(user: models.User, db: AsyncSession):
    limits = USAGE_LIMITS.get(user.subscription_plan, {})
    sub = await db.get(models.Subscription, user.id)
    return {
        "projects": ((sub.projects_used if sub else 0), limits.get("projects")),
        "documents": ((sub.documents_uploaded if sub else 0), limits.get("documents")),
        "ai_queries": ((sub.queries_made if sub else 0), limits.get("ai_queries")),
        "trial_expired": is_trial_expired(user)
    }
