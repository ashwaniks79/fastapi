from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Subscription, User
from app.constants import TIER_FEATURES
from datetime import datetime, timedelta
import stripe
import os
import logging

router = APIRouter()

# Load environment variables
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Logger config
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        logger.info(f" Event received: {event['type']}")

    except Exception as e:
        logger.error(f" Invalid webhook signature: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            logger.info(f" Checkout session completed: {session['id']}")

            metadata = session.get("metadata", {})
            logger.info(f" Metadata: {metadata}")
                                                                   
            user_id = metadata.get("user_id")
            tier = metadata.get("tier")

            if not user_id or not tier:
                logger.warning(" Missing metadata: user_id or tier")
                return {"status": "metadata missing"}

            user = await db.get(User, user_id)
            if not user:
                logger.warning(f" User not found: {user_id}")
                return {"status": "user not found"}

            stripe_sub_id = session.get("subscription")
            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)

            # Update user
            user.subscription_plan = tier.lower()
            user.stripe_customer_id = session.get("customer")

            # Update subscription
            subscription = await db.get(Subscription, user.id)
            if not subscription:
                subscription = Subscription(subscription_id=user.id)
                db.add(subscription)

            subscription.subscriptions_plan = tier.lower()
            subscription.active = True
            subscription.start_date = datetime.utcnow()
            subscription.end_date = datetime.utcnow() + timedelta(days=30)
            subscription.features_enabled = TIER_FEATURES.get(tier.lower(), [])
            subscription.projects_used = 0
            subscription.documents_uploaded = 0
            subscription.queries_made = 0
            subscription.trial_used = True

            await db.commit()
            logger.info(f" Plan upgraded to {tier} for user {user_id}")

        elif event["type"] == "invoice.paid":
            invoice = event["data"]["object"]
            logger.info(f" Invoice paid: {invoice['id']} for customer: {invoice['customer']}")

            # TODO: Add logic to confirm payment and extend subscription if needed

        elif event["type"] == "customer.subscription.created":
            subscription = event["data"]["object"]
            logger.info(f" Subscription created: {subscription['id']} for customer: {subscription['customer']}")

            # Optional: Record in DB, if you want to track all subscriptions

        elif event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            logger.info(f" Payment succeeded: {payment_intent['id']} amount={payment_intent['amount_received']}")

            # Optional: Add any custom payment success logic

        else:
            logger.info(f" Ignored event type: {event['type']}")

    except Exception as e:
        logger.error(f" Error processing event {event['type']}: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook handling failed")

    return {"status": "success", "event": event["type"]}
