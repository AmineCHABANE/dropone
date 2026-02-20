"""
DropOne — Dynamic Product Catalog v3
Auto-syncs from CJ Dropshipping API every 6 hours.
No more fake products — everything is real, orderable, and priced from CJ.
"""

import os
import json
import time
import asyncio
import logging
import hashlib
from typing import Optional

logger = logging.getLogger("dropone.catalog")

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
CACHE_TTL = 6 * 3600  # Refresh every 6 hours
MARGIN_MULTIPLIER = 2.5  # Sell at 2.5x CJ cost (60% margin)
MIN_MARGIN_MULTIPLIER = 2.0  # Minimum 2x (50% margin)
MAX_PRICE = 99.99  # Cap suggested price
PRODUCTS_PER_QUERY = 8  # Products to keep per search query

# Category search queries — curated for high-margin trending products
CATEGORY_QUERIES = {
    "tech": [
        "LED strip lights RGB",
        "wireless earbuds bluetooth",
        "phone holder car magnetic",
        "portable bluetooth speaker",
        "smart watch fitness",
        "ring light tripod",
        "power bank 20000mah",
        "wireless charging pad",
        "mini projector portable",
        "mechanical keyboard RGB",
    ],
    "beauty": [
        "ice roller face massager",
        "jade gua sha roller",
        "LED face mask therapy",
        "hair curler automatic",
        "teeth whitening kit",
        "derma roller",
        "blackhead remover vacuum",
        "makeup brush set",
        "eyelash curler heated",
        "scalp massager brush",
    ],
    "home": [
        "LED neon sign",
        "moon lamp 3D",
        "mushroom table lamp",
        "aroma diffuser ultrasonic",
        "shower steamer aromatherapy",
        "floating shelf wall",
        "LED candles flameless",
        "desk organizer bamboo",
        "cloud light lamp",
        "star projector galaxy",
    ],
    "fitness": [
        "massage gun mini portable",
        "resistance bands set",
        "jump rope speed",
        "yoga mat thick",
        "ab roller wheel",
        "grip strength trainer",
        "foam roller muscle",
        "wrist wraps gym",
    ],
    "kitchen": [
        "electric milk frother",
        "silicone cooking utensils set",
        "portable blender USB",
        "knife sharpener kitchen",
        "vegetable chopper dicer",
        "coffee scale digital",
        "ice cube tray silicone",
        "spice organizer rack",
    ],
    "pet": [
        "pet hair remover roller",
        "cat brush self cleaning",
        "dog water bottle portable",
        "cat toy interactive",
        "pet grooming glove",
        "dog poop bag dispenser",
        "cat scratching post",
        "pet feeding bowl slow",
    ],
    "fashion": [
        "sunglasses polarized",
        "crossbody bag small",
        "minimalist watch",
        "silk scrunchie set",
        "beanie hat winter",
        "phone case leather",
        "tote bag canvas",
        "belt bag fanny pack",
    ],
    "auto": [
        "car vacuum mini cordless",
        "dash cam 1080p",
        "car interior LED strip",
        "car phone mount",
        "car freshener solar",
        "seat gap filler",
        "car trash can",
        "tire inflator portable",
    ],
}

# Tags assigned by category
CATEGORY_TAGS = {
    "tech": ["gadget", "trending"],
    "beauty": ["skincare", "trending", "tiktok"],
    "home": ["decor", "cozy"],
    "fitness": ["workout", "health"],
    "kitchen": ["cooking", "home"],
    "pet": ["pet", "animal"],
    "fashion": ["style", "everyday"],
    "auto": ["car", "auto"],
}

# ---------------------------------------------------------------------------
# CACHE
# ---------------------------------------------------------------------------
_cache = {
    "products": [],
    "last_sync": 0,
    "syncing": False,
}


# ---------------------------------------------------------------------------
# CJ PRODUCT TRANSFORM
# ---------------------------------------------------------------------------
def _parse_price(price_str) -> float:
    """Parse CJ price which can be '12.50' or '12.50 -- 15.00' (range)."""
    if not price_str:
        return 0.0
    s = str(price_str).strip()
    # Range format: "12.50 -- 15.00" → take lowest
    if "--" in s:
        parts = s.split("--")
        try:
            return float(parts[0].strip())
        except (ValueError, IndexError):
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _transform_cj_product(cj_product: dict, category: str, query: str, index: int) -> dict:
    """Transform a CJ API product into DropOne catalog format."""
    pid = cj_product.get("pid", "")
    name = cj_product.get("productNameEn", "Unknown Product")
    image = cj_product.get("productImage", "")
    cost = _parse_price(cj_product.get("sellPrice", 0))

    if cost <= 0:
        return None

    # Calculate pricing with margin
    suggested = round(cost * MARGIN_MULTIPLIER, 2)
    if suggested > MAX_PRICE:
        suggested = MAX_PRICE
    if suggested < cost * MIN_MARGIN_MULTIPLIER:
        suggested = round(cost * MIN_MARGIN_MULTIPLIER, 2)

    margin_pct = round((1 - cost / suggested) * 100) if suggested > 0 else 0

    # Generate stable ID from pid
    stable_id = f"cj-{hashlib.md5(pid.encode()).hexdigest()[:8]}"

    # Collect images
    images = [image] if image else []
    for img in cj_product.get("productImageSet", [])[:4]:
        url = img.get("imageUrl", "") if isinstance(img, dict) else str(img)
        if url and url not in images:
            images.append(url)

    # Clean up name (truncate if too long)
    if len(name) > 60:
        name = name[:57] + "..."

    # Trending score based on position in results (first = more trending)
    trending_score = max(60, 95 - index * 4)

    # Shipping estimate
    shipping = "7-14 days"
    weight = cj_product.get("productWeight", 0)
    if isinstance(weight, str):
        try:
            weight = float(weight)
        except ValueError:
            weight = 0

    tags = list(CATEGORY_TAGS.get(category, ["trending"]))
    # Add extra tags based on query keywords
    for kw in ["LED", "wireless", "bluetooth", "smart", "mini", "portable"]:
        if kw.lower() in query.lower() or kw.lower() in name.lower():
            tags.append(kw.lower())
    tags = list(set(tags))[:5]

    return {
        "id": stable_id,
        "cj_pid": pid,
        "cj_vid": "",  # Filled on order time from product detail
        "name": name,
        "category": category,
        "cost": round(cost, 2),
        "suggested_price": suggested,
        "margin_pct": margin_pct,
        "images": images[:5],
        "short_desc": cj_product.get("description", name)[:120],
        "tags": tags,
        "supplier": "cj_dropshipping",
        "shipping_time": shipping,
        "weight_g": int(weight * 1000) if weight < 50 else int(weight),
        "trending_score": trending_score,
    }


# ---------------------------------------------------------------------------
# SYNC FROM CJ
# ---------------------------------------------------------------------------
async def sync_catalog():
    """Fetch products from CJ API and rebuild catalog."""
    if _cache["syncing"]:
        logger.info("Catalog sync already in progress, skipping")
        return

    _cache["syncing"] = True
    logger.info("Starting CJ catalog sync...")

    try:
        # Import here to avoid circular imports
        import cj_client

        all_products = []
        seen_pids = set()

        for category, queries in CATEGORY_QUERIES.items():
            for query in queries:
                try:
                    results = await cj_client.search_products(query, page=1, page_size=PRODUCTS_PER_QUERY)
                    for idx, cj_prod in enumerate(results):
                        pid = cj_prod.get("pid", "")
                        if pid in seen_pids:
                            continue
                        seen_pids.add(pid)

                        product = _transform_cj_product(cj_prod, category, query, idx)
                        if product and product["cost"] > 0:
                            all_products.append(product)

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.3)

                except Exception as e:
                    logger.warning(f"CJ search failed for '{query}': {e}")
                    continue

        if all_products:
            # Sort by trending score within each category
            all_products.sort(key=lambda p: (p["category"], -p["trending_score"]))

            _cache["products"] = all_products
            _cache["last_sync"] = time.time()
            logger.info(f"CJ catalog sync complete: {len(all_products)} products across {len(set(p['category'] for p in all_products))} categories")
        else:
            logger.error("CJ sync returned 0 products — keeping previous cache")

    except Exception as e:
        logger.error(f"Catalog sync error: {e}")
    finally:
        _cache["syncing"] = False


async def ensure_catalog():
    """Make sure catalog is loaded. Called before any catalog access."""
    now = time.time()
    if not _cache["products"] or (now - _cache["last_sync"]) > CACHE_TTL:
        await sync_catalog()


# ---------------------------------------------------------------------------
# PUBLIC API — same interface as old catalog.py
# ---------------------------------------------------------------------------
PRODUCTS = _cache["products"]  # Live reference (updates when cache updates)


def _get_products() -> list:
    """Always return current cached products."""
    return _cache["products"]


def get_product(product_id: str) -> Optional[dict]:
    for p in _get_products():
        if p["id"] == product_id:
            return p
    return None


def get_product_by_cj_pid(cj_pid: str) -> Optional[dict]:
    for p in _get_products():
        if p.get("cj_pid") == cj_pid:
            return p
    return None


def get_trending(limit: int = 20) -> list[dict]:
    return sorted(_get_products(), key=lambda p: p["trending_score"], reverse=True)[:limit]


def search_products(query: str) -> list[dict]:
    q = query.lower()
    return [
        p for p in _get_products()
        if q in f"{p['name']} {p.get('short_desc','')} {p['category']} {' '.join(p['tags'])}".lower()
    ]


def get_categories() -> list[str]:
    return sorted(set(p["category"] for p in _get_products()))


def get_products_by_category(category: str) -> list[dict]:
    return [p for p in _get_products() if p["category"] == category]


def get_catalog_stats() -> dict:
    products = _get_products()
    return {
        "total_products": len(products),
        "categories": len(set(p["category"] for p in products)),
        "last_sync": _cache["last_sync"],
        "cache_age_minutes": round((time.time() - _cache["last_sync"]) / 60, 1) if _cache["last_sync"] else None,
        "next_sync_minutes": round((CACHE_TTL - (time.time() - _cache["last_sync"])) / 60, 1) if _cache["last_sync"] else 0,
        "avg_margin": round(sum(p["margin_pct"] for p in products) / len(products), 1) if products else 0,
    }
