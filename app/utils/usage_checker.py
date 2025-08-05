from datetime import datetime
from app.constants import USAGE_LIMITS

def is_trial_expired(user):
    if user.subscription_plan != "free":
        return False
    if not user.trial_expiry_date:
        return False
    return datetime.utcnow() > user.trial_expiry_date

def check_usage_limit(user, usage_type):
    limits = USAGE_LIMITS.get(user.subscription_plan, {})
    used = getattr(user, f"{usage_type}_used", 0)
    allowed = limits.get(usage_type)
    if allowed is None:
        return False
    return used >= allowed

def usage_summary(user):
    limits = USAGE_LIMITS.get(user.subscription_plan, {})
    return {
        "projects": (user.projects_used, limits.get("projects")),
        "documents": (user.documents_uploaded, limits.get("documents")),
        "ai_queries": (user.ai_queries_made, limits.get("ai_queries")),
        "trial_expired": is_trial_expired(user)
    }
