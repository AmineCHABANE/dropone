"""
DropOne — Dynamic Product Catalog v4.0
Auto-syncs from CJ Dropshipping API.
- Supabase persistent cache (survives Vercel cold starts)
- Concurrent API calls (fits in 10s Vercel timeout)
- Weekly cron sync with query rotation (Set A / Set B every 2 weeks)
- Dead product cleanup (removes 404 / out-of-stock)
- Callable via external cron (cron-job.org)
"""

import os
import json
import time
import asyncio
import logging
import hashlib
from datetime import datetime
from typing import Optional

logger = logging.getLogger("dropone.catalog")

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
CACHE_TTL = 7 * 24 * 3600   # 7 days (weekly sync)
MARGIN_MULTIPLIER = 2.5      # 60% margin
MIN_MARGIN_MULTIPLIER = 2.0
MAX_PRICE = 99.99
PRODUCTS_PER_QUERY = 10
CONCURRENT_BATCH = 24        # All queries at once (16 max with 2 per cat)

# ---------------------------------------------------------------------------
# QUERY ROTATION — Set A / Set B alternate every 2 weeks
# Keeps the catalog fresh without losing best-sellers
# ---------------------------------------------------------------------------
CATEGORY_QUERIES_A = {
    "tech": ["earbuds wireless", "phone accessories"],
    "beauty": ["face massager", "skincare tool"],
    "home": ["LED lamp", "home decor"],
    "fitness": ["massage gun", "fitness accessories"],
    "kitchen": ["kitchen gadget", "portable blender"],
    "pet": ["pet grooming", "dog accessories"],
    "fashion": ["sunglasses women", "crossbody bag"],
    "auto": ["car accessories", "car LED"],
}

CATEGORY_QUERIES_B = {
    "tech": ["smart watch", "bluetooth speaker"],
    "beauty": ["LED face mask", "hair accessories"],
    "home": ["moon lamp", "humidifier"],
    "fitness": ["yoga accessories", "resistance bands"],
    "kitchen": ["egg cooker", "electric grinder"],
    "pet": ["cat toy", "pet feeder"],
    "fashion": ["minimalist watch", "tote bag"],
    "auto": ["car phone mount", "dash cam"],
}


def _get_active_queries() -> dict:
    """Return Set A or Set B based on ISO week number (rotates every 2 weeks)."""
    week = datetime.utcnow().isocalendar()[1]
    if (week // 2) % 2 == 0:
        return CATEGORY_QUERIES_A
    return CATEGORY_QUERIES_B


def _get_active_set_name() -> str:
    week = datetime.utcnow().isocalendar()[1]
    return "A" if (week // 2) % 2 == 0 else "B"


# Backwards-compatible default
CATEGORY_QUERIES = CATEGORY_QUERIES_A

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

# In-memory cache (fast reads within same request/container)
_cache = {
    "products": [],
    "last_sync": 0,
    "syncing": False,
}


# ---------------------------------------------------------------------------
# SUPABASE PERSISTENT CACHE
# ---------------------------------------------------------------------------
def _supabase_headers():
    key = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_ANON_KEY", ""))
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _supabase_url():
    return os.getenv("SUPABASE_URL", "").rstrip("/")


def _save_to_supabase(products: list):
    """Persist catalog to Supabase for cold start recovery."""
    import httpx
    url = _supabase_url()
    if not url:
        return
    try:
        blob = json.dumps({
            "products": products,
            "synced_at": time.time(),
            "query_set": _get_active_set_name(),
            "product_count": len(products),
        })
        httpx.post(
            f"{url}/rest/v1/kv_cache",
            headers={**_supabase_headers(), "Prefer": "resolution=merge-duplicates"},
            json={"id": "cj_catalog", "value": blob},
            timeout=5,
        )
        logger.info(f"Saved {len(products)} products to Supabase cache (set {_get_active_set_name()})")
    except Exception as e:
        logger.warning(f"Supabase cache save failed: {e}")


def _load_from_supabase() -> tuple:
    """Load catalog from Supabase. Returns (products, synced_at)."""
    import httpx
    url = _supabase_url()
    if not url:
        return [], 0
    try:
        resp = httpx.get(
            f"{url}/rest/v1/kv_cache",
            headers=_supabase_headers(),
            params={"id": "eq.cj_catalog", "select": "value"},
            timeout=5,
        )
        rows = resp.json()
        if rows and rows[0].get("value"):
            data = json.loads(rows[0]["value"])
            products = data.get("products", [])
            synced_at = data.get("synced_at", 0)
            logger.info(f"Loaded {len(products)} from Supabase (age: {(time.time()-synced_at)/3600:.1f}h)")
            return products, synced_at
    except Exception as e:
        logger.warning(f"Supabase cache load failed: {e}")
    return [], 0


def _save_sync_log(stats: dict):
    """Save sync history for monitoring."""
    import httpx
    url = _supabase_url()
    if not url:
        return
    try:
        blob = json.dumps(stats)
        httpx.post(
            f"{url}/rest/v1/kv_cache",
            headers={**_supabase_headers(), "Prefer": "resolution=merge-duplicates"},
            json={"id": f"sync_log_{int(time.time())}", "value": blob},
            timeout=5,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CJ PRODUCT TRANSFORM
# ---------------------------------------------------------------------------
def _parse_price(price_str) -> float:
    if not price_str:
        return 0.0
    s = str(price_str).strip()
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


def _transform(cj_product: dict, category: str, query: str, index: int) -> Optional[dict]:
    """Transform CJ API product to DropOne format."""
    pid = cj_product.get("pid", "")
    name = cj_product.get("productNameEn", "")
    image = cj_product.get("productImage", "")
    cost = _parse_price(cj_product.get("sellPrice", 0))

    if cost <= 0 or not name:
        return None

    suggested = min(round(cost * MARGIN_MULTIPLIER, 2), MAX_PRICE)
    if suggested < cost * MIN_MARGIN_MULTIPLIER:
        suggested = round(cost * MIN_MARGIN_MULTIPLIER, 2)
    margin_pct = round((1 - cost / suggested) * 100) if suggested > 0 else 0

    stable_id = f"cj-{hashlib.md5(pid.encode()).hexdigest()[:8]}"

    images = [image] if image else []
    for img in cj_product.get("productImageSet", [])[:3]:
        u = img.get("imageUrl", "") if isinstance(img, dict) else str(img)
        if u and u not in images:
            images.append(u)

    if len(name) > 60:
        name = name[:57] + "..."

    tags = list(CATEGORY_TAGS.get(category, ["trending"]))
    for kw in ["LED", "wireless", "bluetooth", "smart", "mini", "portable"]:
        if kw.lower() in name.lower():
            tags.append(kw.lower())
    tags = list(set(tags))[:5]

    weight = cj_product.get("productWeight", 0)
    if isinstance(weight, str):
        try:
            weight = float(weight)
        except ValueError:
            weight = 0

    return {
        "id": stable_id,
        "cj_pid": pid,
        "cj_vid": "",
        "name": name,
        "category": category,
        "cost": round(cost, 2),
        "suggested_price": suggested,
        "margin_pct": margin_pct,
        "images": images[:4],
        "short_desc": (cj_product.get("description") or name)[:120],
        "tags": tags,
        "supplier": "cj_dropshipping",
        "shipping_time": "7-14 days",
        "weight_g": int(weight * 1000) if weight < 50 else int(weight),
        "trending_score": max(60, 95 - index * 5),
    }


# ---------------------------------------------------------------------------
# DEAD PRODUCT CLEANUP
# ---------------------------------------------------------------------------
async def _check_product_alive(cj_client_mod, cj_pid: str) -> bool:
    """Check if a CJ product still exists and has variants."""
    try:
        detail = await cj_client_mod.get_product(cj_pid)
        if not detail:
            return False
        variants = detail.get("variants", [])
        return bool(variants)
    except Exception:
        return False


async def cleanup_dead_products(max_checks: int = 30) -> dict:
    """Remove products that are dead on CJ (404 / no variants).

    Checks a batch each sync to stay within API limits.
    """
    import cj_client as cj_mod

    products = _cache["products"]
    if not products:
        return {"checked": 0, "removed": 0, "alive": 0, "dead_names": []}

    to_check = products[:max_checks]
    dead_pids = set()
    alive_count = 0

    # Check in batches of 5
    for i in range(0, len(to_check), 5):
        batch = to_check[i:i+5]
        tasks = [_check_product_alive(cj_mod, p["cj_pid"]) for p in batch]
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=15.0,
            )
            for p, result in zip(batch, results):
                if isinstance(result, Exception) or not result:
                    dead_pids.add(p["cj_pid"])
                    logger.info(f"Dead product: {p['name']} ({p['cj_pid']})")
                else:
                    alive_count += 1
        except asyncio.TimeoutError:
            logger.warning("Cleanup batch timed out, skipping rest")
            break

    # Remove dead
    dead_names = [p["name"] for p in to_check if p["cj_pid"] in dead_pids]
    if dead_pids:
        before = len(products)
        _cache["products"] = [p for p in products if p["cj_pid"] not in dead_pids]
        logger.info(f"Cleaned {before - len(_cache['products'])} dead products")

    return {
        "checked": alive_count + len(dead_pids),
        "removed": len(dead_pids),
        "alive": alive_count,
        "dead_names": dead_names,
    }


# ---------------------------------------------------------------------------
# SYNC
# ---------------------------------------------------------------------------
async def _fetch_query(cj_client_mod, query: str, category: str) -> list:
    """Fetch one CJ query, return transformed products."""
    try:
        results = await cj_client_mod.search_products(query, page=1, page_size=PRODUCTS_PER_QUERY)
        products = []
        for idx, cj_prod in enumerate(results):
            p = _transform(cj_prod, category, query, idx)
            if p:
                products.append(p)
        return products
    except Exception as e:
        logger.warning(f"CJ query '{query}' failed: {e}")
        return []


async def sync_catalog(use_rotation: bool = False):
    """Sync catalog from CJ API using concurrent requests.

    Args:
        use_rotation: If True, uses the rotating query set (A/B).
    """
    if _cache["syncing"]:
        return
    _cache["syncing"] = True

    queries = _get_active_queries() if use_rotation else CATEGORY_QUERIES
    set_name = _get_active_set_name() if use_rotation else "A"
    logger.info(f"Starting CJ catalog sync (set {set_name})...")

    try:
        import cj_client as cj_mod

        tasks = []
        for category, query_list in queries.items():
            for query in query_list:
                tasks.append((query, category))

        all_products = []
        seen_pids = set()

        for i in range(0, len(tasks), CONCURRENT_BATCH):
            batch = tasks[i:i + CONCURRENT_BATCH]
            coros = [_fetch_query(cj_mod, q, cat) for q, cat in batch]
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*coros, return_exceptions=True),
                    timeout=8.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Batch {i//CONCURRENT_BATCH + 1} timed out")
                break

            for result in results:
                if isinstance(result, Exception):
                    continue
                for p in result:
                    if p["cj_pid"] not in seen_pids:
                        seen_pids.add(p["cj_pid"])
                        all_products.append(p)

        if all_products:
            all_products.sort(key=lambda p: (p["category"], -p["trending_score"]))
            _cache["products"] = all_products
            _cache["last_sync"] = time.time()

            try:
                _save_to_supabase(all_products)
            except Exception:
                pass

            logger.info(f"CJ sync OK: {len(all_products)} products, "
                        f"{len(set(p['category'] for p in all_products))} categories (set {set_name})")
        else:
            logger.error("CJ sync: 0 products returned, keeping previous cache")

    except Exception as e:
        logger.error(f"Catalog sync error: {e}")
    finally:
        _cache["syncing"] = False


async def weekly_sync() -> dict:
    """Full weekly sync: rotate queries + fetch + cleanup dead products.

    Called by /api/cron/catalog-sync (external cron, 1x/week).
    Returns detailed stats for logging.
    """
    start = time.time()
    old_count = len(_cache["products"])

    # Step 1: Sync with rotated queries
    await sync_catalog(use_rotation=True)
    new_count = len(_cache["products"])

    # Step 2: Clean dead products
    cleanup_stats = {"checked": 0, "removed": 0, "alive": 0, "dead_names": []}
    try:
        cleanup_stats = await cleanup_dead_products(max_checks=30)
        if cleanup_stats["removed"] > 0:
            _save_to_supabase(_cache["products"])
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

    final_count = len(_cache["products"])
    elapsed = round(time.time() - start, 1)

    stats = {
        "success": True,
        "elapsed_seconds": elapsed,
        "query_set": _get_active_set_name(),
        "products_before": old_count,
        "products_fetched": new_count,
        "products_after_cleanup": final_count,
        "cleanup": cleanup_stats,
        "categories": len(set(p["category"] for p in _cache["products"])) if _cache["products"] else 0,
        "synced_at": datetime.utcnow().isoformat() + "Z",
    }

    try:
        _save_sync_log(stats)
    except Exception:
        pass

    logger.info(f"Weekly sync done in {elapsed}s: {final_count} products "
                f"(fetched={new_count}, removed={cleanup_stats['removed']})")
    return stats


async def ensure_catalog():
    """Load catalog — from memory, then Supabase, then CJ API."""
    now = time.time()

    # 1. In-memory cache still fresh?
    if _cache["products"] and (now - _cache["last_sync"]) < CACHE_TTL:
        return

    # 2. Try Supabase persistent cache
    if not _cache["products"]:
        products, synced_at = _load_from_supabase()
        if products and (now - synced_at) < CACHE_TTL:
            _cache["products"] = products
            _cache["last_sync"] = synced_at
            logger.info(f"Catalog loaded from Supabase: {len(products)} products")
            return
        elif products:
            _cache["products"] = products
            _cache["last_sync"] = synced_at
            logger.info(f"Stale catalog from Supabase: {len(products)} products, will refresh")

    # 3. Sync from CJ API
    await sync_catalog()


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------
def _get_products() -> list:
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
    now = time.time()
    return {
        "total_products": len(products),
        "categories": len(set(p["category"] for p in products)),
        "last_sync": _cache["last_sync"],
        "cache_age_hours": round((now - _cache["last_sync"]) / 3600, 1) if _cache["last_sync"] else None,
        "next_sync_hours": round((CACHE_TTL - (now - _cache["last_sync"])) / 3600, 1) if _cache["last_sync"] else 0,
        "avg_margin": round(sum(p["margin_pct"] for p in products) / len(products), 1) if products else 0,
        "query_set": _get_active_set_name(),
        "source": "supabase_cache" if _cache["last_sync"] else "empty",
    }
