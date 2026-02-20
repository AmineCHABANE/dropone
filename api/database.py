"""
DropOne — Supabase Database Layer v2 (REST)
Uses direct REST API calls via httpx — no heavy SDK dependency.
Every call wrapped in try/except. Never crashes the API.
"""

import os
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
import httpx

logger = logging.getLogger("dropone.db")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def _rest(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"

def _get(table: str, params: dict = None) -> list:
    try:
        r = httpx.get(_rest(table), headers=_headers(), params=params or {}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"GET {table}: {e}")
        return []

def _post(table: str, data: dict) -> list:
    try:
        r = httpx.post(_rest(table), headers=_headers(), json=data, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"POST {table}: {e}")
        return []

def _patch(table: str, params: dict, data: dict) -> list:
    try:
        r = httpx.patch(_rest(table), headers=_headers(), params=params, json=data, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"PATCH {table}: {e}")
        return []

def _delete(table: str, params: dict):
    try:
        r = httpx.delete(_rest(table), headers=_headers(), params=params, timeout=10)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"DELETE {table}: {e}")


# ============================================================================
# USERS
# ============================================================================
def get_or_create_user(email: str) -> dict:
    try:
        rows = _get("users", {"email": f"eq.{email}", "select": "*"})
        if rows:
            return rows[0]
        user = {"email": email, "total_earnings": 0, "xp": 0, "level": 1}
        res = _post("users", user)
        return res[0] if res else user
    except Exception as e:
        logger.error(f"get_or_create_user({email}): {e}")
        return {"email": email, "total_earnings": 0, "xp": 0, "level": 1}


def get_user(email: str) -> Optional[dict]:
    try:
        rows = _get("users", {"email": f"eq.{email}", "select": "*"})
        return rows[0] if rows else None
    except Exception as e:
        logger.error(f"get_user: {e}")
        return None


def update_user_earnings(email: str, amount: float):
    try:
        user = get_user(email)
        if user:
            new = round(float(user.get("total_earnings") or 0) + amount, 2)
            _patch("users", {"email": f"eq.{email}"}, {"total_earnings": new})
    except Exception as e:
        logger.error(f"update_user_earnings: {e}")


def update_user_xp(email: str, xp_gained: int, badges: list = None):
    try:
        user = get_user(email)
        if not user:
            return
        new_xp = int(user.get("xp") or 0) + xp_gained
        new_level = _calc_level(new_xp)
        upd = {"xp": new_xp, "level": new_level}
        if badges:
            existing = user.get("badges") or []
            if isinstance(existing, str):
                existing = json.loads(existing)
            upd["badges"] = list(set(existing + badges))
        _patch("users", {"email": f"eq.{email}"}, upd)
    except Exception as e:
        logger.error(f"update_user_xp: {e}")


def update_user_streak(email: str):
    try:
        user = get_user(email)
        if not user:
            return
        today = datetime.utcnow().strftime("%Y-%m-%d")
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        last = str(user.get("last_sale_date") or "")[:10]
        if last == yesterday:
            streak = int(user.get("streak_days") or 0) + 1
        elif last == today:
            streak = max(int(user.get("streak_days") or 1), 1)
        else:
            streak = 1
        _patch("users", {"email": f"eq.{email}"}, {"streak_days": streak, "last_sale_date": today})
    except Exception as e:
        logger.error(f"update_user_streak: {e}")


def _calc_level(xp: int) -> int:
    level = 1
    while level < 50 and xp >= int(100 * ((level + 1) ** 1.5)):
        level += 1
    return level


# ============================================================================
# STORES
# ============================================================================
def create_store(data: dict) -> dict:
    try:
        res = _post("stores", data)
        return res[0] if res else data
    except Exception as e:
        logger.error(f"create_store: {e}")
        return data


def get_store(slug: str) -> Optional[dict]:
    try:
        rows = _get("stores", {"slug": f"eq.{slug}", "select": "*"})
        return rows[0] if rows else None
    except Exception as e:
        logger.error(f"get_store({slug}): {e}")
        return None


def slug_exists(slug: str) -> bool:
    try:
        rows = _get("stores", {"slug": f"eq.{slug}", "select": "slug"})
        return bool(rows)
    except Exception:
        return False


def get_user_stores(email: str) -> list[dict]:
    try:
        return _get("stores", {"owner_email": f"eq.{email}", "select": "*", "order": "created_at.desc"})
    except Exception as e:
        logger.error(f"get_user_stores: {e}")
        return []


def update_store(slug: str, updates: dict):
    try:
        _patch("stores", {"slug": f"eq.{slug}"}, updates)
    except Exception as e:
        logger.error(f"update_store: {e}")


def increment_store_sales(slug: str, margin: float):
    try:
        store = get_store(slug)
        if store:
            _patch("stores", {"slug": f"eq.{slug}"}, {
                "total_sales": int(store.get("total_sales") or 0) + 1,
                "total_revenue": round(float(store.get("total_revenue") or 0) + margin, 2),
            })
    except Exception as e:
        logger.error(f"increment_store_sales: {e}")


def get_store_owner(slug: str) -> Optional[str]:
    store = get_store(slug)
    return store.get("owner_email") if store else None


# ============================================================================
# ORDERS
# ============================================================================
def create_order(data: dict) -> dict:
    try:
        res = _post("orders", data)
        return res[0] if res else data
    except Exception as e:
        logger.error(f"create_order: {e}")
        return data


def get_order(order_id: str) -> Optional[dict]:
    try:
        rows = _get("orders", {"order_id": f"eq.{order_id}", "select": "*"})
        return rows[0] if rows else None
    except Exception as e:
        logger.error(f"get_order: {e}")
        return None


def get_store_orders(slug: str) -> list[dict]:
    try:
        return _get("orders", {"store_slug": f"eq.{slug}", "select": "*", "order": "created_at.desc"})
    except Exception as e:
        logger.error(f"get_store_orders: {e}")
        return []


def get_all_orders_for_user(email: str) -> list[dict]:
    try:
        stores = get_user_stores(email)
        slugs = [s["slug"] for s in stores]
        if not slugs:
            return []
        # Supabase REST: in filter
        slug_filter = ",".join(slugs)
        return _get("orders", {"store_slug": f"in.({slug_filter})", "select": "*", "order": "created_at.desc"})
    except Exception as e:
        logger.error(f"get_all_orders_for_user: {e}")
        return []


def update_order(order_id: str, updates: dict):
    try:
        _patch("orders", {"order_id": f"eq.{order_id}"}, updates)
    except Exception as e:
        logger.error(f"update_order: {e}")


def get_order_stats(email: str) -> dict:
    orders = get_all_orders_for_user(email)
    statuses = {}
    rev = margin = 0.0
    for o in orders:
        s = o.get("status", "pending")
        statuses[s] = statuses.get(s, 0) + 1
        rev += float(o.get("amount_paid") or 0)
        margin += float(o.get("seller_margin") or 0)
    return {"total_orders": len(orders), "by_status": statuses,
            "total_revenue": round(rev, 2), "total_margin": round(margin, 2)}


# ============================================================================
# ANALYTICS
# ============================================================================
def track_view(store_slug: str, ip: str, user_agent: str, referrer: str):
    try:
        _post("analytics_views", {
            "store_slug": store_slug,
            "ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else "",
            "user_agent": (user_agent or "")[:500],
            "referrer": (referrer or "")[:500],
            "source": _detect_source(referrer),
            "device": _detect_device(user_agent),
        })
    except Exception as e:
        logger.error(f"track_view: {e}")


def track_conversion(store_slug: str, order_id: str, amount: float):
    try:
        _post("analytics_conversions", {
            "store_slug": store_slug, "order_id": order_id, "amount": amount,
        })
    except Exception as e:
        logger.error(f"track_conversion: {e}")


def get_analytics(store_slug: str, period: str = "7d") -> dict:
    empty = {"period": period, "total_views": 0, "total_conversions": 0,
             "total_revenue": 0, "conversion_rate": 0, "sources": {},
             "devices": {}, "daily_views": []}
    try:
        cutoff = _period_dt(period).isoformat()
        views = _get("analytics_views", {
            "store_slug": f"eq.{store_slug}", "created_at": f"gte.{cutoff}",
            "select": "source,device,created_at"
        })
        convs = _get("analytics_conversions", {
            "store_slug": f"eq.{store_slug}", "created_at": f"gte.{cutoff}",
            "select": "amount,created_at"
        })
        tv, tc = len(views), len(convs)
        rev = sum(float(c.get("amount") or 0) for c in convs)
        srcs, devs, daily = {}, {}, {}
        for v in views:
            s = v.get("source", "direct")
            srcs[s] = srcs.get(s, 0) + 1
            d = v.get("device", "unknown")
            devs[d] = devs.get(d, 0) + 1
            day = (v.get("created_at") or "")[:10]
            if day:
                daily[day] = daily.get(day, 0) + 1
        return {"period": period, "total_views": tv, "total_conversions": tc,
                "total_revenue": round(rev, 2),
                "conversion_rate": round(tc / max(tv, 1) * 100, 2),
                "sources": srcs, "devices": devs,
                "daily_views": [{"date": k, "views": v} for k, v in sorted(daily.items())]}
    except Exception as e:
        logger.error(f"get_analytics: {e}")
        return empty


def _detect_source(ref: str) -> str:
    if not ref:
        return "direct"
    r = ref.lower()
    for kw, name in [("tiktok","tiktok"),("instagram","instagram"),("ig.me","instagram"),
                     ("facebook","facebook"),("fb.me","facebook"),("twitter","twitter"),
                     ("x.com","twitter"),("google","google"),("youtube","youtube"),
                     ("whatsapp","whatsapp"),("wa.me","whatsapp"),("snapchat","snapchat")]:
        if kw in r:
            return name
    return "other"


def _detect_device(ua: str) -> str:
    if not ua:
        return "unknown"
    u = ua.lower()
    if any(k in u for k in ("mobile","android","iphone")):
        return "mobile"
    if any(k in u for k in ("tablet","ipad")):
        return "tablet"
    return "desktop"


def _period_dt(period: str) -> datetime:
    now = datetime.utcnow()
    if period == "24h":
        return now - timedelta(hours=24)
    return now - timedelta(days={"7d":7,"30d":30,"90d":90}.get(period, 7))


# ============================================================================
# PUSH SUBSCRIPTIONS
# ============================================================================
def save_push_subscription(email: str, subscription: dict):
    try:
        existing = _get("push_subscriptions", {"email": f"eq.{email}", "select": "id"})
        if existing:
            _patch("push_subscriptions", {"email": f"eq.{email}"}, {"subscription": subscription})
        else:
            _post("push_subscriptions", {"email": email, "subscription": subscription})
    except Exception as e:
        logger.error(f"save_push_subscription: {e}")


def get_push_subscriptions(email: str) -> list[dict]:
    try:
        rows = _get("push_subscriptions", {"email": f"eq.{email}", "select": "subscription"})
        return [r["subscription"] for r in rows if r.get("subscription")]
    except Exception as e:
        logger.error(f"get_push_subscriptions: {e}")
        return []


def remove_push_subscription(email: str):
    try:
        _delete("push_subscriptions", {"email": f"eq.{email}"})
    except Exception as e:
        logger.error(f"remove_push_subscription: {e}")


# ============================================================================
# SELLER NETWORK
# ============================================================================
def record_network_sale(product_id: str, product_name: str, category: str,
                        amount: float, seller_email: str, source: str = "direct"):
    try:
        _post("network_sales", {
            "product_id": product_id, "product_name": product_name,
            "category": category, "amount": amount,
            "seller_email": seller_email, "source": source,
        })
        _upsert_product_stats(product_id, product_name, category, sales_delta=1, revenue_delta=amount)
    except Exception as e:
        logger.error(f"record_network_sale: {e}")


def record_network_view(product_id: str):
    try:
        s = _get("network_product_stats", {"product_id": f"eq.{product_id}", "select": "total_views"})
        if s:
            _patch("network_product_stats", {"product_id": f"eq.{product_id}"}, {
                "total_views": int(s[0].get("total_views") or 0) + 1
            })
    except Exception as e:
        logger.error(f"record_network_view: {e}")


def record_network_store_created(product_id: str, product_name: str = "", category: str = ""):
    _upsert_product_stats(product_id, product_name, category, stores_delta=1)


def _upsert_product_stats(pid: str, name: str, cat: str,
                           sales_delta: int = 0, revenue_delta: float = 0, stores_delta: int = 0):
    try:
        ex = _get("network_product_stats", {"product_id": f"eq.{pid}", "select": "*"})
        if ex:
            r = ex[0]
            _patch("network_product_stats", {"product_id": f"eq.{pid}"}, {
                "total_sales": int(r.get("total_sales") or 0) + sales_delta,
                "total_revenue": round(float(r.get("total_revenue") or 0) + revenue_delta, 2),
                "stores_count": int(r.get("stores_count") or 0) + stores_delta,
                "product_name": name or r.get("product_name", ""),
            })
        else:
            _post("network_product_stats", {
                "product_id": pid, "product_name": name, "category": cat,
                "total_views": 0, "total_sales": sales_delta,
                "total_revenue": revenue_delta, "stores_count": stores_delta,
            })
    except Exception as e:
        logger.error(f"_upsert_product_stats: {e}")


def get_network_trending(period: str = "7d", limit: int = 10) -> list[dict]:
    try:
        cutoff = _period_dt(period).isoformat()
        sales = _get("network_sales", {
            "created_at": f"gte.{cutoff}",
            "select": "product_id,product_name,category,amount"
        })
        if not sales:
            return []
        prods = {}
        for s in sales:
            pid = s["product_id"]
            if pid not in prods:
                prods[pid] = {"product_id": pid, "product_name": s.get("product_name") or pid,
                              "category": s.get("category") or "", "sales_count": 0, "revenue": 0.0}
            prods[pid]["sales_count"] += 1
            prods[pid]["revenue"] += float(s.get("amount") or 0)

        stats = _get("network_product_stats", {"select": "*"})
        sm = {s["product_id"]: s for s in stats}
        out = []
        for pid, d in prods.items():
            st = sm.get(pid, {})
            views = int(st.get("total_views") or 0)
            cr = round(d["sales_count"] / max(views, 1) * 100, 2)
            d.update({"revenue": round(d["revenue"], 2), "stores_selling": int(st.get("stores_count") or 0),
                       "conversion_rate": cr, "velocity_label": "🔥 En hausse",
                       "trending_score": d["sales_count"] * 10 + cr * 5})
            out.append(d)
        out.sort(key=lambda x: x["trending_score"], reverse=True)
        return out[:limit]
    except Exception as e:
        logger.error(f"get_network_trending: {e}")
        return []


def get_network_sources() -> list[dict]:
    try:
        cutoff = _period_dt("30d").isoformat()
        views = _get("analytics_views", {
            "created_at": f"gte.{cutoff}", "select": "source,store_slug"
        })
        convs = _get("analytics_conversions", {
            "created_at": f"gte.{cutoff}", "select": "store_slug"
        })
        conv_slugs = set(c["store_slug"] for c in convs)
        src = {}
        for v in views:
            s = v.get("source", "direct")
            if s not in src:
                src[s] = {"total_traffic": 0, "conversions": 0}
            src[s]["total_traffic"] += 1
            if v.get("store_slug") in conv_slugs:
                src[s]["conversions"] += 1
        out = []
        for name, d in src.items():
            t = d["total_traffic"]
            out.append({"source": name, "total_traffic": t, "conversions": d["conversions"],
                         "conversion_rate": round(d["conversions"] / max(t, 1) * 100, 1)})
        out.sort(key=lambda x: x["total_traffic"], reverse=True)
        return out
    except Exception as e:
        logger.error(f"get_network_sources: {e}")
        return []


def get_network_leaderboard(limit: int = 20) -> list[dict]:
    try:
        rows = _get("users", {
            "select": "email,xp,level,badges,streak_days,total_earnings",
            "xp": "gt.0", "order": "xp.desc", "limit": str(limit)
        })
        board = []
        for i, u in enumerate(rows):
            email = u.get("email", "")
            p = email.split("@")[0] if "@" in email else "user"
            display = p[0].upper() + "***" + p[-1] if len(p) > 1 else "A***"
            level = int(u.get("level") or 1)
            board.append({"rank": i + 1, "display_name": display, "level": level,
                           "level_name": _level_name(level), "xp": int(u.get("xp") or 0),
                           "total_sales": 0, "badges": u.get("badges") or [],
                           "streak_days": int(u.get("streak_days") or 0)})
        return board
    except Exception as e:
        logger.error(f"get_network_leaderboard: {e}")
        return []


def get_seller_profile(email: str) -> dict:
    user = get_user(email)
    if not user:
        return {"level": 1, "level_name": "🌱 Débutant", "xp": 0, "total_sales": 0,
                "total_revenue": 0, "badges": [], "streak_days": 0,
                "next_level_xp": 100, "progress_pct": 0}
    level = int(user.get("level") or 1)
    xp = int(user.get("xp") or 0)
    next_xp = int(100 * ((level + 1) ** 1.5))
    cur_xp = int(100 * (level ** 1.5))
    progress = (xp - cur_xp) / max(next_xp - cur_xp, 1) * 100
    return {"level": level, "level_name": _level_name(level), "xp": xp, "total_sales": 0,
            "total_revenue": round(float(user.get("total_earnings") or 0), 2),
            "badges": user.get("badges") or [], "streak_days": int(user.get("streak_days") or 0),
            "next_level_xp": next_xp, "progress_pct": round(min(progress, 100), 1)}


def _level_name(level: int) -> str:
    if level <= 2: return "🌱 Débutant"
    if level <= 5: return "📦 Vendeur"
    if level <= 10: return "⭐ Pro"
    if level <= 20: return "🔥 Expert"
    if level <= 35: return "💎 Master"
    return "👑 Légende"
