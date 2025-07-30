# app/constants.py

TIER_PRICING = {
    "free": 0.00,
    "silver": 29.99,
    "gold": 49.99
}

# Coupon codes (optional)
COUPONS = {
    "DISCOUNT50": 0.50,
    "FREETRIAL": 1.00
}

# Features by tier
TIER_FEATURES = {
    "free": ['Access to 3 Basic Agents', 'Limited Usage of Tools'],
    "silver": ['Access to All Standard Agents', 'Limited Media/Marketing Tools'],
    "gold": ['Full Access to 50+ Agents', 'Includes Document, Vision, Marketing Tools']
}

# Stripe Price IDs (replace with real ones from Stripe Dashboard)
STRIPE_PRICE_IDS = {
    "silver": "price_1Rpo9HGmURqtLVT55UAcVCxc",
    "gold": "price_1RpoB3GmURqtLVT5DLd8fwET"
}
