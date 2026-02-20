"""
DropOne — Product Catalog
Curated dropshipping products with supplier costs & suggested retail prices.
In production, this connects to CJ Dropshipping / Zendrop / Spocket APIs.
"""

from typing import Optional

# ---------------------------------------------------------------------------
# Product catalog — trending items with real-ish pricing
# ---------------------------------------------------------------------------
PRODUCTS = [
    # --- Tech & Gadgets ---
    {
        "id": "tech-001",
        "name": "LED Sunset Lamp",
        "category": "tech",
        "cost": 4.50,
        "suggested_price": 24.99,
        "margin_pct": 62,
        "images": [
            "https://images.unsplash.com/photo-1573790387438-4da905039392?w=600",
        ],
        "short_desc": "Viral TikTok sunset projector lamp — 16 colors, USB powered",
        "tags": ["trending", "tiktok", "home"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-14 days",
        "weight_g": 350,
        "trending_score": 95,
    },
    {
        "id": "tech-002",
        "name": "Magnetic Phone Mount Pro",
        "category": "tech",
        "cost": 3.20,
        "suggested_price": 19.99,
        "margin_pct": 68,
        "images": [
            "https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=600",
        ],
        "short_desc": "360° magnetic car phone holder — universal, one-hand use",
        "tags": ["auto", "gadget", "everyday"],
        "supplier": "cj_dropshipping",
        "shipping_time": "5-12 days",
        "weight_g": 120,
        "trending_score": 88,
    },
    {
        "id": "tech-003",
        "name": "Mini Portable Projector",
        "category": "tech",
        "cost": 28.00,
        "suggested_price": 89.99,
        "margin_pct": 62,
        "images": [
            "https://images.unsplash.com/photo-1478720568477-152d9b164e26?w=600",
        ],
        "short_desc": "HD mini projector — WiFi, 100-inch display, built-in speaker",
        "tags": ["trending", "entertainment", "gift"],
        "supplier": "zendrop",
        "shipping_time": "8-15 days",
        "weight_g": 680,
        "trending_score": 91,
    },
    {
        "id": "tech-004",
        "name": "Wireless Earbuds Pro",
        "category": "tech",
        "cost": 6.80,
        "suggested_price": 34.99,
        "margin_pct": 72,
        "images": [
            "https://images.unsplash.com/photo-1590658268037-6bf12f032f55?w=600",
        ],
        "short_desc": "TWS Bluetooth 5.3 — ANC, 30h battery, touch control",
        "tags": ["audio", "everyday", "gift"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-12 days",
        "weight_g": 55,
        "trending_score": 87,
    },

    # --- Home & Living ---
    {
        "id": "home-001",
        "name": "Cloud LED Neon Sign",
        "category": "home",
        "cost": 5.80,
        "suggested_price": 29.99,
        "margin_pct": 71,
        "images": [
            "https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=600",
        ],
        "short_desc": "Aesthetic cloud neon light — USB powered, wall-mountable",
        "tags": ["trending", "tiktok", "decor"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-14 days",
        "weight_g": 280,
        "trending_score": 93,
    },
    {
        "id": "home-002",
        "name": "Levitating Plant Pot",
        "category": "home",
        "cost": 15.00,
        "suggested_price": 59.99,
        "margin_pct": 67,
        "images": [
            "https://images.unsplash.com/photo-1459411552884-841db9b3cc2a?w=600",
        ],
        "short_desc": "Magnetic floating planter — rotates, LED base, real plant compatible",
        "tags": ["trending", "gift", "luxury"],
        "supplier": "zendrop",
        "shipping_time": "10-18 days",
        "weight_g": 950,
        "trending_score": 86,
    },
    {
        "id": "home-003",
        "name": "Smart Aroma Diffuser",
        "category": "home",
        "cost": 8.50,
        "suggested_price": 39.99,
        "margin_pct": 71,
        "images": [
            "https://images.unsplash.com/photo-1602928321679-560bb453f190?w=600",
        ],
        "short_desc": "500ml ultrasonic diffuser — 7 LED colors, timer, whisper quiet",
        "tags": ["wellness", "home", "gift"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-14 days",
        "weight_g": 420,
        "trending_score": 82,
    },
    {
        "id": "home-004",
        "name": "Galaxy Star Projector",
        "category": "home",
        "cost": 9.00,
        "suggested_price": 44.99,
        "margin_pct": 72,
        "images": [
            "https://images.unsplash.com/photo-1534796636912-3b95b3ab5986?w=600",
        ],
        "short_desc": "Nebula projector — Bluetooth speaker, remote, 360° rotation",
        "tags": ["trending", "tiktok", "bedroom"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-14 days",
        "weight_g": 380,
        "trending_score": 94,
    },

    # --- Fashion & Accessories ---
    {
        "id": "fashion-001",
        "name": "Minimalist Watch",
        "category": "fashion",
        "cost": 7.50,
        "suggested_price": 39.99,
        "margin_pct": 73,
        "images": [
            "https://images.unsplash.com/photo-1524592094714-0f0654e20314?w=600",
        ],
        "short_desc": "Ultra-thin quartz watch — genuine leather band, water resistant",
        "tags": ["fashion", "gift", "classic"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-14 days",
        "weight_g": 45,
        "trending_score": 79,
    },
    {
        "id": "fashion-002",
        "name": "Blue Light Glasses",
        "category": "fashion",
        "cost": 2.20,
        "suggested_price": 19.99,
        "margin_pct": 80,
        "images": [
            "https://images.unsplash.com/photo-1574258495973-f010dfbb5371?w=600",
        ],
        "short_desc": "Anti-fatigue computer glasses — UV400, lightweight, unisex",
        "tags": ["trending", "health", "everyday"],
        "supplier": "cj_dropshipping",
        "shipping_time": "5-10 days",
        "weight_g": 25,
        "trending_score": 85,
    },
    {
        "id": "fashion-003",
        "name": "Crossbody Phone Bag",
        "category": "fashion",
        "cost": 4.00,
        "suggested_price": 24.99,
        "margin_pct": 76,
        "images": [
            "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600",
        ],
        "short_desc": "Minimalist leather phone sling — RFID blocking, 6 card slots",
        "tags": ["trending", "fashion", "everyday"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-12 days",
        "weight_g": 150,
        "trending_score": 83,
    },

    # --- Beauty & Wellness ---
    {
        "id": "beauty-001",
        "name": "Ice Roller Face Massager",
        "category": "beauty",
        "cost": 1.80,
        "suggested_price": 14.99,
        "margin_pct": 80,
        "images": [
            "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=600",
        ],
        "short_desc": "Stainless steel ice roller — depuffs, tightens, morning routine essential",
        "tags": ["trending", "tiktok", "skincare"],
        "supplier": "cj_dropshipping",
        "shipping_time": "5-10 days",
        "weight_g": 180,
        "trending_score": 92,
    },
    {
        "id": "beauty-002",
        "name": "LED Face Mask Pro",
        "category": "beauty",
        "cost": 12.00,
        "suggested_price": 49.99,
        "margin_pct": 68,
        "images": [
            "https://images.unsplash.com/photo-1596755389378-c31d21fd1273?w=600",
        ],
        "short_desc": "7-color LED therapy — anti-aging, acne, rejuvenation",
        "tags": ["trending", "skincare", "luxury"],
        "supplier": "zendrop",
        "shipping_time": "8-15 days",
        "weight_g": 220,
        "trending_score": 89,
    },
    {
        "id": "beauty-003",
        "name": "Scalp Massager Shampoo Brush",
        "category": "beauty",
        "cost": 1.20,
        "suggested_price": 12.99,
        "margin_pct": 83,
        "images": [
            "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=600",
        ],
        "short_desc": "Silicone scalp brush — promotes growth, exfoliates, spa feeling",
        "tags": ["tiktok", "haircare", "cheap"],
        "supplier": "cj_dropshipping",
        "shipping_time": "5-10 days",
        "weight_g": 60,
        "trending_score": 88,
    },

    # --- Fitness ---
    {
        "id": "fit-001",
        "name": "Massage Gun Mini",
        "category": "fitness",
        "cost": 11.00,
        "suggested_price": 49.99,
        "margin_pct": 70,
        "images": [
            "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=600",
        ],
        "short_desc": "Portable percussion massager — 6 heads, 30 speeds, USB-C",
        "tags": ["trending", "fitness", "gift"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-14 days",
        "weight_g": 380,
        "trending_score": 90,
    },
    {
        "id": "fit-002",
        "name": "Resistance Bands Set (5x)",
        "category": "fitness",
        "cost": 3.50,
        "suggested_price": 22.99,
        "margin_pct": 76,
        "images": [
            "https://images.unsplash.com/photo-1598289431512-b97b0917affc?w=600",
        ],
        "short_desc": "5 levels, latex-free, carry bag — gym & home workout",
        "tags": ["fitness", "everyday", "cheap"],
        "supplier": "cj_dropshipping",
        "shipping_time": "5-10 days",
        "weight_g": 200,
        "trending_score": 75,
    },
    {
        "id": "fit-003",
        "name": "Smart Water Bottle",
        "category": "fitness",
        "cost": 6.00,
        "suggested_price": 29.99,
        "margin_pct": 72,
        "images": [
            "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600",
        ],
        "short_desc": "LED temperature display — reminds you to drink, 500ml insulated",
        "tags": ["trending", "health", "gift"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-12 days",
        "weight_g": 320,
        "trending_score": 84,
    },

    # --- Pet ---
    {
        "id": "pet-001",
        "name": "Self-Cleaning Cat Brush",
        "category": "pet",
        "cost": 2.50,
        "suggested_price": 16.99,
        "margin_pct": 78,
        "images": [
            "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=600",
        ],
        "short_desc": "One-click hair removal — gentle, ergonomic, all coat types",
        "tags": ["trending", "tiktok", "pet"],
        "supplier": "cj_dropshipping",
        "shipping_time": "5-10 days",
        "weight_g": 90,
        "trending_score": 91,
    },
    {
        "id": "pet-002",
        "name": "Interactive Dog Ball",
        "category": "pet",
        "cost": 5.00,
        "suggested_price": 24.99,
        "margin_pct": 72,
        "images": [
            "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=600",
        ],
        "short_desc": "Auto-rolling smart ball — LED, rechargeable, keeps pets active",
        "tags": ["trending", "pet", "gift"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-12 days",
        "weight_g": 200,
        "trending_score": 86,
    },

    # --- Kids ---
    {
        "id": "kids-001",
        "name": "LCD Writing Tablet",
        "category": "kids",
        "cost": 3.80,
        "suggested_price": 19.99,
        "margin_pct": 73,
        "images": [
            "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=600",
        ],
        "short_desc": "12-inch digital drawing pad — colorful, one-button erase, no mess",
        "tags": ["kids", "educational", "gift"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-12 days",
        "weight_g": 180,
        "trending_score": 83,
    },

    # --- Car ---
    {
        "id": "car-001",
        "name": "Car Vacuum Cleaner Mini",
        "category": "auto",
        "cost": 8.00,
        "suggested_price": 34.99,
        "margin_pct": 69,
        "images": [
            "https://images.unsplash.com/photo-1449965408869-ebd13bc9e5d8?w=600",
        ],
        "short_desc": "Cordless, 9000PA suction — USB-C, HEPA filter, wet & dry",
        "tags": ["auto", "gadget", "practical"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-14 days",
        "weight_g": 450,
        "trending_score": 81,
    },

    # --- High-ticket ---
    {
        "id": "premium-001",
        "name": "Smart Home Security Camera",
        "category": "tech",
        "cost": 18.00,
        "suggested_price": 69.99,
        "margin_pct": 66,
        "images": [
            "https://images.unsplash.com/photo-1558002038-1055907df827?w=600",
        ],
        "short_desc": "2K WiFi camera — night vision, motion alerts, 2-way audio, cloud/SD",
        "tags": ["home", "security", "smart"],
        "supplier": "zendrop",
        "shipping_time": "8-15 days",
        "weight_g": 250,
        "trending_score": 80,
    },
    {
        "id": "premium-002",
        "name": "Electric Neck Massager",
        "category": "wellness",
        "cost": 14.00,
        "suggested_price": 59.99,
        "margin_pct": 69,
        "images": [
            "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=600",
        ],
        "short_desc": "EMS pulse + heat therapy — 6 modes, portable, USB-C rechargeable",
        "tags": ["trending", "wellness", "gift"],
        "supplier": "cj_dropshipping",
        "shipping_time": "7-14 days",
        "weight_g": 200,
        "trending_score": 87,
    },
]

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def get_product(product_id: str) -> Optional[dict]:
    for p in PRODUCTS:
        if p["id"] == product_id:
            return p
    return None


def get_trending(limit: int = 20) -> list[dict]:
    return sorted(PRODUCTS, key=lambda p: p["trending_score"], reverse=True)[:limit]


def search_products(query: str) -> list[dict]:
    q = query.lower()
    results = []
    for p in PRODUCTS:
        searchable = f"{p['name']} {p['short_desc']} {p['category']} {' '.join(p['tags'])}".lower()
        if q in searchable:
            results.append(p)
    return results


def get_categories() -> list[str]:
    return list(set(p["category"] for p in PRODUCTS))
