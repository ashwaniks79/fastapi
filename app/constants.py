# app/constants.py

# Plan Pricing (monthly per person)
TIER_PRICING = {
    "free": 0.00,
    "silver": 25.00,   # updated from 29.99
    "gold": 32.00      # updated from 49.99
}

# Optional coupon support
COUPONS = {
    "DISCOUNT50": 0.50,
    "FREETRIAL": 1.00
}

# Stripe Price IDs (replace with real IDs from Stripe)
STRIPE_PRICE_IDS = {
    "free": None,
    "silver": "price_1Rqvp6GmURqtLVT55QKLJulL",
    "gold": "price_1RqvqOGmURqtLVT5tR9YfWpB"
}

# Feature access by tier
TIER_FEATURES = {
    "free": [
        'Access to 3 Basic Agents',
        'Limited Usage of Tools',
        '3 Projects Max',
        '5 Document Uploads',
        '50 AI Queries',
    ],
    "silver": [
        'All Free Plan Features',
        'Field Service Module',
        'Document Controls',
        'Timesheet Access',
        'Basic Scheduling & Task Management',
        '50 Projects',
        '100 Documents',
        '1000 AI Queries'
    ],
    "gold": [
        'Everything in Silver',
        'Project Gantt Planning',
        'Document Sign',
        'Advanced Analytics',
        'Priority Support',
        'Unlimited Projects & Documents',
        'Essentially Unlimited AI Queries'
    ]
}

# Usage limits per tier
USAGE_LIMITS = {
    "free": {
        "projects": 3,
        "documents": 5,
        "ai_queries": 50,
        "trial_days": 5
    },
    "silver": {
        "projects": 50,
        "documents": 100,
        "ai_queries": 1000
    },
    "gold": {
        "projects": 99999,
        "documents": 99999,
        "ai_queries": 99999
    }
}

# Placeholder for future add-ons
FUTURE_ADDONS = {
    "extra_agents": False,
    "extra_storage": False
}
