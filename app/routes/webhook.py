from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Subscription, User
from app.constants import TIER_FEATURES
from datetime import datetime, timedelta
import stripe
import os

router = APIRouter()

# Set API key and secret
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        print("Session data:", session) 
        metadata = session.get("metadata", {})
        print("Metadata received:", metadata)
        user_id = metadata.get("user_id")
        tier = metadata.get("tier")

        if not user_id or not tier:
            raise HTTPException(status_code=400, detail="Missing user_id or tier in metadata")

        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        stripe_sub_id = session.get("subscription")
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)

        user.subscription_plan = tier.lower()
        user.stripe_customer_id = session.get("customer")

        subscription = await db.get(Subscription, user.id)
        if not subscription:
            subscription = Subscription(subscription_id=user.id)
            db.add(subscription)

        subscription.subscriptions_plan = tier.lower()
        subscription.active = True
        subscription.start_date = datetime.utcnow()
        subscription.end_date = datetime.utcnow() + timedelta(days=30)
        subscription.features_enabled = TIER_FEATURES[tier]
        subscription.projects_used = 0
        subscription.documents_uploaded = 0
        subscription.queries_made = 0
        subscription.trial_used = True

        await db.commit()

        return {"status": "success"}

    # Handle other events gracefully
    return {"status": "ignored", "event": event["type"]}
