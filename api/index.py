import sys, os
sys.path.insert(0, os.path.dirname(__file__))
"""
DropOne — Production Backend API v2
FastAPI + Supabase + OpenAI + Stripe + PayPal
18 bugs fixed from v1 audit.
"""

import os
import re
import json
import uuid
import time
import asyncio
import hashlib
from urllib.parse import quote as url_quote
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, field_validator
import stripe
from openai import OpenAI

import database as db
from catalog import PRODUCTS, get_product, get_trending, search_products
from store_generator import generate_store, generate_store_page, generate_success_page
from content_ai import generate_content, calculate_ad_budget
from multi_store import get_collections, get_collection, suggest_upsells, generate_collection_with_ai
from notifications import PushManager
import cj_client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")
APP_URL = os.getenv("APP_URL", "https://dropone.vercel.app").rstrip("/")
COMMISSION_RATE = float(os.getenv("COMMISSION_RATE", "0.08"))

stripe.api_key = STRIPE_SECRET_KEY
ai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
push_mgr = PushManager()
PAYPAL_BASE = "https://api-m.paypal.com" if PAYPAL_MODE == "live" else "https://api-m.sandbox.paypal.com"

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("dropone")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="DropOne API", version="2.1.0")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
_rate_limits: dict[str, list[float]] = {}

def _check_rate_limit(key: str, max_req: int = 5, window: int = 60) -> bool:
    now = time.time()
    _rate_limits.setdefault(key, [])
    _rate_limits[key] = [t for t in _rate_limits[key] if now - t < window]
    if len(_rate_limits[key]) >= max_req:
        return False
    _rate_limits[key].append(now)
    return True


# ---------------------------------------------------------------------------
# Models — FIX #12: email validation
# ---------------------------------------------------------------------------
EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

class CreateStoreRequest(BaseModel):
    product_id: str
    user_email: str
    store_name: Optional[str] = None
    custom_price: Optional[float] = None

    @field_validator("user_email")
    @classmethod
    def validate_email(cls, v):
        if not EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v.lower().strip()

class StoreResponse(BaseModel):
    store_id: str
    slug: str
    url: str
    store_name: str
    product: dict
    seller_price: float
    supplier_cost: float
    margin: float
    margin_pct: float

class CheckoutRequest(BaseModel):
    store_slug: str
    customer_name: str = ""
    customer_email: str = ""
    shipping_address: dict = {}
    payment_method: str = "stripe"


# ---------------------------------------------------------------------------
# FIX #6: Root route
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return RedirectResponse(url="/app")

@app.get("/app")
async def serve_app():
    """Serve the PWA — Vercel handles this via static routing."""
    return RedirectResponse(url="/index.html")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.2.0",
        "services": {
            "ai": bool(ai_client),
            "stripe": bool(STRIPE_SECRET_KEY),
            "paypal": bool(PAYPAL_CLIENT_ID),
            "supabase": bool(os.getenv("SUPABASE_URL")),
            "cj": bool(os.getenv("CJ_API_KEY")),
            "push": bool(os.getenv("VAPID_PUBLIC_KEY")),
        },
    }


# ---------------------------------------------------------------------------
# Public Config (safe to expose)
# ---------------------------------------------------------------------------
@app.get("/api/config")
async def get_config():
    """Return public-safe config for the frontend."""
    return {
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
        "app_url": APP_URL,
        "google_auth_enabled": bool(os.getenv("SUPABASE_ANON_KEY")),
        "categories": sorted(set(p["category"] for p in PRODUCTS)),
        "total_products": len(PRODUCTS),
    }


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------
@app.get("/api/products")
async def list_products(category: Optional[str] = None, sort: str = "trending",
                        q: Optional[str] = None, limit: int = 20, offset: int = 0):
    if q:
        prods = search_products(q)
    elif category:
        prods = [p for p in PRODUCTS if p["category"] == category]
    else:
        prods = get_trending() if sort == "trending" else PRODUCTS
    total = len(prods)
    return {"products": prods[offset:offset + limit], "total": total,
            "categories": sorted(set(p["category"] for p in PRODUCTS))}


@app.get("/api/products/{product_id}")
async def get_product_detail(product_id: str):
    p = get_product(product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    return p


# ---------------------------------------------------------------------------
# Store Creation — FIX #5: max slug attempts
# ---------------------------------------------------------------------------
@app.post("/api/stores/create", response_model=StoreResponse)
async def create_store_endpoint(req: CreateStoreRequest):
    if not _check_rate_limit(f"create:{req.user_email}", max_req=5, window=60):
        raise HTTPException(429, "Trop de boutiques créées. Attends une minute.")

    product = get_product(req.product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    store_data = await generate_store(product=product, custom_name=req.store_name, ai_client=ai_client)

    supplier_cost = product["cost"]
    seller_price = req.custom_price or product["suggested_price"]
    if seller_price < supplier_cost * 1.1:
        seller_price = round(supplier_cost * 2, 2)

    commission = round(seller_price * COMMISSION_RATE, 2)
    margin = round(seller_price - supplier_cost - commission, 2)
    margin_pct = round((margin / seller_price) * 100, 1)

    # FIX #5: cap slug attempts at 20
    slug = store_data["slug"]
    for attempt in range(1, 21):
        if not db.slug_exists(slug):
            break
        slug = f"{store_data['slug']}-{attempt}"
    else:
        slug = f"{store_data['slug']}-{uuid.uuid4().hex[:6]}"

    db.get_or_create_user(req.user_email)

    store_id = str(uuid.uuid4())[:8]
    db.create_store({
        "store_id": store_id, "slug": slug, "owner_email": req.user_email,
        "store_name": store_data["name"], "tagline": store_data["tagline"],
        "logo_emoji": store_data["logo_emoji"],
        "color_primary": store_data["color_primary"],
        "color_accent": store_data["color_accent"],
        "product_id": product["id"], "product_data": product,
        "product_description": store_data["product_description"],
        "selling_points": store_data["selling_points"],
        "seller_price": seller_price, "supplier_cost": supplier_cost,
        "commission": commission, "margin": margin, "margin_pct": margin_pct,
    })

    db.record_network_store_created(product["id"], product["name"], product.get("category", ""))

    return StoreResponse(
        store_id=store_id, slug=slug, url=f"{APP_URL}/s/{slug}",
        store_name=store_data["name"], product=product,
        seller_price=seller_price, supplier_cost=supplier_cost,
        margin=margin, margin_pct=margin_pct,
    )


@app.get("/api/stores/{slug}")
async def get_store_endpoint(slug: str):
    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found")
    return store


@app.get("/api/stores/{slug}/orders")
async def get_store_orders(slug: str):
    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found")
    return {"orders": db.get_store_orders(slug)}


@app.get("/api/user/{email}/stores")
async def get_user_stores(email: str):
    user = db.get_user(email)
    if not user:
        return {"stores": [], "total_earnings": 0}
    stores = db.get_user_stores(email)
    return {"stores": stores, "total_earnings": round(float(user.get("total_earnings") or 0), 2)}


# FIX #14: single endpoint for all user orders (frontend was doing N requests)
@app.get("/api/user/{email}/orders")
async def get_user_orders(email: str):
    orders = db.get_all_orders_for_user(email)
    stats = db.get_order_stats(email)
    return {"orders": orders, "stats": stats}


# ---------------------------------------------------------------------------
# Public Store Page
# ---------------------------------------------------------------------------
@app.get("/s/{slug}", response_class=HTMLResponse)
async def store_page(slug: str, request: Request):
    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found")
    if not store.get("active", True):
        raise HTTPException(404, "Store is currently offline")

    ip = request.headers.get("x-forwarded-for", request.headers.get("x-real-ip", ""))
    if not ip and request.client:
        ip = request.client.host

    db.track_view(
        store_slug=slug, ip=ip,
        user_agent=request.headers.get("user-agent", ""),
        referrer=request.headers.get("referer", ""),
    )
    db.record_network_view(store.get("product_id", ""))

    product = store.get("product_data", {})
    store_for_page = {**store, "product": product}
    html = generate_store_page(store_for_page, paypal_client_id=PAYPAL_CLIENT_ID)
    return HTMLResponse(content=html)


# FIX #7: Success page after payment
@app.get("/s/{slug}/success", response_class=HTMLResponse)
async def store_success(slug: str, request: Request):
    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found")

    product = store.get("product_data", {})
    paypal_order_id = request.query_params.get("token", "")

    # If PayPal return, capture payment server-side
    if paypal_order_id:
        try:
            await _capture_paypal(paypal_order_id, store)
        except Exception as e:
            logger.error(f"PayPal auto-capture on return failed: {e}")

    html = generate_success_page(store, product)
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Checkout — Stripe
# ---------------------------------------------------------------------------
@app.post("/api/checkout/create")
async def create_checkout(req: CheckoutRequest):
    store = db.get_store(req.store_slug)
    if not store:
        raise HTTPException(404, "Store not found")
    if not store.get("active", True):
        raise HTTPException(400, "Store is currently offline")

    product = store.get("product_data", {})
    price_cents = int(float(store["seller_price"]) * 100)

    if req.payment_method == "paypal":
        return await _create_paypal_order(store, product, req)

    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "Stripe not configured")

    try:
        # Check if seller has Stripe Connect account
        seller = db.get_user(store.get("owner_email", ""))
        stripe_account_id = seller.get("stripe_account_id") if seller else None

        session_params = {
            "mode": "payment",
            "line_items": [{
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": product.get("name", "Produit"),
                        "description": store.get("tagline", ""),
                        "images": product.get("images", [])[:1],
                    },
                    "unit_amount": price_cents,
                },
                "quantity": 1,
            }],
            "shipping_address_collection": {
                "allowed_countries": [
                    "FR","BE","CH","DE","ES","IT","NL","GB","US","CA",
                    "PT","AT","IE","LU","SE","DK","NO","FI","PL",
                ],
            },
            "customer_email": req.customer_email or None,
            "success_url": f"{APP_URL}/s/{req.store_slug}/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{APP_URL}/s/{req.store_slug}",
            "metadata": {
                "store_slug": req.store_slug,
                "store_id": store["store_id"],
                "product_id": store.get("product_id", ""),
                "supplier_cost": str(store["supplier_cost"]),
                "commission": str(store["commission"]),
                "seller_margin": str(store["margin"]),
            },
        }

        # If seller has Stripe Connect → direct payout via destination charge
        if stripe_account_id:
            commission_cents = int(float(store["commission"]) * 100)
            supplier_cents = int(float(store["supplier_cost"]) * 100)
            platform_fee = commission_cents + supplier_cents  # DropOne keeps commission + supplier cost
            session_params["payment_intent_data"] = {
                "application_fee_amount": platform_fee,
                "transfer_data": {"destination": stripe_account_id},
            }

        session = stripe.checkout.Session.create(**session_params)
        return {"checkout_url": session.url, "session_id": session.id, "provider": "stripe"}
    except stripe.StripeError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------------------
# Checkout — PayPal — FIX #4: custom_id < 127 chars
# ---------------------------------------------------------------------------
async def _get_paypal_token() -> str:
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{PAYPAL_BASE}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def _create_paypal_order(store: dict, product: dict, req: CheckoutRequest) -> dict:
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise HTTPException(500, "PayPal not configured")

    import httpx
    token = await _get_paypal_token()
    price = f"{float(store['seller_price']):.2f}"

    # FIX #4: custom_id max 127 chars — use compact format
    custom = f"{req.store_slug}|{store['store_id']}|{store['supplier_cost']}|{store['commission']}|{store['margin']}"
    custom = custom[:127]

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{PAYPAL_BASE}/v2/checkout/orders",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": req.store_slug[:127],
                    "description": product.get("name", "Produit")[:127],
                    "amount": {"currency_code": "EUR", "value": price},
                    "custom_id": custom,
                }],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "brand_name": "DropOne",
                            "return_url": f"{APP_URL}/s/{req.store_slug}/success?token={{id}}",
                            "cancel_url": f"{APP_URL}/s/{req.store_slug}",
                            "user_action": "PAY_NOW",
                            "shipping_preference": "GET_FROM_FILE",
                        }
                    }
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()

    approve_url = ""
    for link in data.get("links", []):
        if link.get("rel") in ("approve", "payer-action"):
            approve_url = link["href"]
            break

    return {"checkout_url": approve_url, "paypal_order_id": data["id"], "provider": "paypal"}


async def _capture_paypal(paypal_order_id: str, store: dict):
    """Capture PayPal payment and process order."""
    import httpx
    token = await _get_paypal_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{PAYPAL_BASE}/v2/checkout/orders/{paypal_order_id}/capture",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") != "COMPLETED":
        logger.warning(f"PayPal capture not completed: {data.get('status')}")
        return

    unit = data.get("purchase_units", [{}])[0]
    capture = unit.get("payments", {}).get("captures", [{}])[0]
    custom_str = unit.get("custom_id", "")
    parts = custom_str.split("|")

    slug = parts[0] if parts else ""
    supplier_cost = float(parts[2]) if len(parts) > 2 else 0
    commission = float(parts[3]) if len(parts) > 3 else 0
    seller_margin = float(parts[4]) if len(parts) > 4 else 0

    if not slug:
        slug = store.get("slug", "")

    payer = data.get("payer", {})
    amount = float(capture.get("amount", {}).get("value", 0))

    await _process_completed_order(
        store=store,
        customer_email=payer.get("email_address", ""),
        customer_name=payer.get("name", {}).get("given_name", ""),
        shipping_address=payer.get("address", {}),
        amount_paid=amount,
        supplier_cost=supplier_cost,
        commission=commission,
        seller_margin=seller_margin,
        payment_provider="paypal",
        payment_id=paypal_order_id,
    )


@app.post("/api/checkout/paypal/capture/{paypal_order_id}")
async def capture_paypal_endpoint(paypal_order_id: str):
    """Manual PayPal capture endpoint (fallback)."""
    if not PAYPAL_CLIENT_ID:
        raise HTTPException(500, "PayPal not configured")

    import httpx
    token = await _get_paypal_token()
    async with httpx.AsyncClient(timeout=15) as client:
        # First get order details to find the store
        check = await client.get(
            f"{PAYPAL_BASE}/v2/checkout/orders/{paypal_order_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        check.raise_for_status()
        order_data = check.json()

    unit = order_data.get("purchase_units", [{}])[0]
    custom_str = unit.get("custom_id", "")
    parts = custom_str.split("|")
    slug = parts[0] if parts else unit.get("reference_id", "")

    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found for this PayPal order")

    await _capture_paypal(paypal_order_id, store)
    return {"received": True, "status": "captured"}


# ---------------------------------------------------------------------------
# Webhook — Stripe
# ---------------------------------------------------------------------------
@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload)
    except Exception as e:
        raise HTTPException(400, str(e))

    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        meta = session.get("metadata", {})
        slug = meta.get("store_slug", "")
        store = db.get_store(slug)
        if store:
            shipping = session.get("shipping_details", {})
            await _process_completed_order(
                store=store,
                customer_email=session.get("customer_email", ""),
                customer_name=shipping.get("name", ""),
                shipping_address=shipping.get("address", {}),
                amount_paid=session.get("amount_total", 0) / 100,
                supplier_cost=float(meta.get("supplier_cost", 0)),
                commission=float(meta.get("commission", 0)),
                seller_margin=float(meta.get("seller_margin", 0)),
                payment_provider="stripe",
                payment_id=session.get("id", ""),
            )

    return {"received": True}


# ---------------------------------------------------------------------------
# Process completed order (shared Stripe + PayPal)
# ---------------------------------------------------------------------------
async def _process_completed_order(store, customer_email, customer_name,
                                    shipping_address, amount_paid, supplier_cost,
                                    commission, seller_margin, payment_provider, payment_id):
    order_id = f"DO-{uuid.uuid4().hex[:8].upper()}"
    product = store.get("product_data", store.get("product", {}))

    db.create_order({
        "order_id": order_id, "store_slug": store["slug"],
        "product_id": store.get("product_id", product.get("id", "")),
        "product_name": product.get("name", "Produit"),
        "customer_email": customer_email, "customer_name": customer_name,
        "shipping_address": shipping_address, "amount_paid": amount_paid,
        "supplier_cost": supplier_cost, "commission": commission,
        "seller_margin": seller_margin, "status": "pending",
        "payment_provider": payment_provider,
        "payment_session_id": payment_id if payment_provider == "stripe" else None,
        "paypal_order_id": payment_id if payment_provider == "paypal" else None,
    })

    db.increment_store_sales(store["slug"], seller_margin)
    db.update_user_earnings(store["owner_email"], seller_margin)
    db.track_conversion(store["slug"], order_id, amount_paid)

    db.record_network_sale(
        product_id=store.get("product_id", ""),
        product_name=product.get("name", ""),
        category=product.get("category", ""),
        amount=amount_paid,
        seller_email=store["owner_email"],
    )

    xp = 10 + int(amount_paid / 10)
    db.update_user_xp(store["owner_email"], xp)
    db.update_user_streak(store["owner_email"])

    try:
        await push_mgr.notify_sale(
            seller_email=store["owner_email"],
            product_name=product.get("name", ""),
            amount=amount_paid, margin=seller_margin,
            store_name=store.get("store_name", ""), order_id=order_id,
        )
    except Exception as e:
        logger.warning(f"Push failed: {e}")

    logger.info(f"Order {order_id} via {payment_provider}: €{amount_paid}")


# ---------------------------------------------------------------------------
# Webhook — CJ — FIX #16: actually process tracking
# ---------------------------------------------------------------------------
@app.post("/api/webhook/cj")
async def cj_webhook(request: Request):
    payload = await request.json()
    event_type = payload.get("type", "")
    cj_order_id = payload.get("orderId", "")
    tracking = payload.get("trackingNumber", "")
    carrier = payload.get("logisticsName", "")
    status = payload.get("orderStatus", "")

    if not cj_order_id:
        return {"received": True}

    # Find matching order by supplier_order_id
    # Search in recent orders
    logger.info(f"CJ webhook: type={event_type} order={cj_order_id} tracking={tracking}")

    if tracking:
        # Try to find order and update tracking
        try:
            import httpx as _hx
            rows = _hx.get(
                f"{os.getenv('SUPABASE_URL','').rstrip('/')}/rest/v1/orders",
                headers={"apikey": os.getenv("SUPABASE_SERVICE_KEY",""),
                         "Authorization": f"Bearer {os.getenv('SUPABASE_SERVICE_KEY','')}"},
                params={"supplier_order_id": f"eq.{cj_order_id}", "select": "order_id,store_slug"},
                timeout=10
            ).json()
            if rows:
                order = rows[0]
                db.update_order(order["order_id"], {
                    "tracking_number": tracking,
                    "carrier": carrier,
                    "status": "shipped",
                    "shipped_at": datetime.utcnow().isoformat(),
                })
                # Notify seller
                store = db.get_store(order["store_slug"])
                if store:
                    try:
                        await push_mgr.notify_shipped(
                            seller_email=store["owner_email"],
                            order_id=order["order_id"],
                            tracking_number=tracking,
                            product_name=store.get("product_data", {}).get("name", ""),
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"CJ webhook processing: {e}")

    return {"received": True}


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
@app.get("/api/analytics/{slug}")
async def get_analytics(slug: str, period: str = "7d"):
    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found")
    return db.get_analytics(slug, period)


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------
@app.get("/api/push/vapid-key")
async def get_vapid_key():
    key = os.getenv("VAPID_PUBLIC_KEY", "")
    return {"enabled": bool(key), "vapid_public_key": key}


@app.post("/api/push/subscribe")
async def push_subscribe(request: Request):
    body = await request.json()
    email = body.get("email", "")
    sub = body.get("subscription", {})
    if not email or not sub:
        raise HTTPException(400, "email and subscription required")
    db.save_push_subscription(email, sub)
    return {"subscribed": True}


# ---------------------------------------------------------------------------
# Content Generator — FIX #13: concurrent AI calls
# ---------------------------------------------------------------------------
@app.get("/api/content/{slug}/{platform}")
async def get_content(slug: str, platform: str, content_type: str = "organic"):
    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found")
    if not _check_rate_limit(f"content:{slug}:{platform}", max_req=10, window=60):
        raise HTTPException(429, "Too many requests")

    product = store.get("product_data", {})
    return await generate_content(
        product=product,
        store={"slug": slug, "url": f"{APP_URL}/s/{slug}", "seller_price": float(store["seller_price"])},
        platform=platform, content_type=content_type, ai_client=ai_client,
    )


@app.get("/api/content/{slug}/all")
async def get_all_content(slug: str):
    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found")
    if not _check_rate_limit(f"content-all:{slug}", max_req=3, window=60):
        raise HTTPException(429, "Wait a minute")

    product = store.get("product_data", {})
    store_ctx = {"slug": slug, "url": f"{APP_URL}/s/{slug}", "seller_price": float(store["seller_price"])}

    # FIX #13: concurrent AI calls instead of sequential
    tasks = [
        generate_content(product=product, store=store_ctx, platform=p, ai_client=ai_client)
        for p in ["tiktok", "instagram", "facebook", "snapchat"]
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    platforms = ["tiktok", "instagram", "facebook", "snapchat"]
    return {p: (r if not isinstance(r, Exception) else {"error": str(r)})
            for p, r in zip(platforms, results)}


@app.get("/api/content/{slug}/ad-budget")
async def get_ad_budget(slug: str):
    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found")
    return calculate_ad_budget(
        product_price=float(store["seller_price"]),
        supplier_cost=float(store["supplier_cost"]),
        commission_rate=COMMISSION_RATE,
    )


# ---------------------------------------------------------------------------
# Seller Network — FIX #2: add /sources endpoint
# ---------------------------------------------------------------------------
@app.get("/api/network/trending")
async def network_trending(period: str = "7d", limit: int = 10):
    return {"period": period, "products": db.get_network_trending(period=period, limit=limit)}


@app.get("/api/network/sources")
async def network_sources():
    """FIX #2: This endpoint was missing — frontend calls it."""
    return {"sources": db.get_network_sources()}


@app.get("/api/network/leaderboard")
async def network_leaderboard(limit: int = 20):
    return {"leaderboard": db.get_network_leaderboard(limit=limit)}


@app.get("/api/network/profile/{email}")
async def network_profile(email: str):
    return db.get_seller_profile(email)


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------
@app.get("/api/collections")
async def list_collections():
    return {"collections": get_collections()}


@app.get("/api/collections/{collection_id}")
async def get_collection_detail(collection_id: str):
    col = get_collection(collection_id)
    if not col:
        raise HTTPException(404, "Collection not found")
    return col


@app.get("/api/products/{product_id}/upsells")
async def get_upsells(product_id: str, limit: int = 3):
    return {"upsells": suggest_upsells(product_id, limit=limit)}


@app.post("/api/collections/generate")
async def generate_ai_collection(request: Request):
    body = await request.json()
    theme = body.get("theme", "")
    if not theme:
        raise HTTPException(400, "Theme required")
    if not _check_rate_limit("ai-collection", max_req=5, window=60):
        raise HTTPException(429, "Wait a minute")
    col = await generate_collection_with_ai(theme=theme, ai_client=ai_client)
    if not col:
        all_cols = get_collections()
        return all_cols[0] if all_cols else {"error": "Could not generate"}
    return col


@app.post("/api/stores/create-multi")
async def create_multi_store(request: Request):
    body = await request.json()
    collection_id = body.get("collection_id", "")
    user_email = body.get("user_email", "")
    if not collection_id or not user_email:
        raise HTTPException(400, "collection_id and user_email required")
    if not _check_rate_limit(f"multi:{user_email}", max_req=3, window=60):
        raise HTTPException(429, "Wait a minute")

    col = get_collection(collection_id)
    if not col:
        raise HTTPException(404, "Collection not found")

    db.get_or_create_user(user_email)
    created = []

    for product in col["products"]:
        store_data = await generate_store(product=product, ai_client=ai_client)
        slug = store_data["slug"]
        for attempt in range(1, 21):
            if not db.slug_exists(slug):
                break
            slug = f"{store_data['slug']}-{attempt}"
        else:
            slug = f"{store_data['slug']}-{uuid.uuid4().hex[:6]}"

        store_id = str(uuid.uuid4())[:8]
        sp = product["suggested_price"]
        comm = round(sp * COMMISSION_RATE, 2)
        margin = round(sp - product["cost"] - comm, 2)

        db.create_store({
            "store_id": store_id, "slug": slug, "owner_email": user_email,
            "store_name": store_data["name"], "tagline": store_data["tagline"],
            "logo_emoji": store_data["logo_emoji"],
            "color_primary": store_data["color_primary"],
            "color_accent": store_data["color_accent"],
            "product_id": product["id"], "product_data": product,
            "product_description": store_data["product_description"],
            "selling_points": store_data["selling_points"],
            "seller_price": sp, "supplier_cost": product["cost"],
            "commission": comm, "margin": margin,
            "margin_pct": round((margin / sp) * 100, 1),
            "collection_id": collection_id,
        })
        db.record_network_store_created(product["id"], product["name"], product.get("category", ""))
        created.append({"store_id": store_id, "slug": slug, "url": f"{APP_URL}/s/{slug}",
                         "product_name": product["name"], "seller_price": sp, "margin": margin})

    return {"collection": col["name"], "stores_created": len(created),
            "stores": created, "total_potential_margin": round(sum(s["margin"] for s in created), 2)}


# ---------------------------------------------------------------------------
# Store Management — FIX #11: ownership check
# ---------------------------------------------------------------------------
@app.put("/api/stores/{slug}/price")
async def update_price(slug: str, request: Request):
    body = await request.json()
    new_price = float(body.get("new_price", 0))
    email = body.get("email", "")

    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found")
    if email and store.get("owner_email") != email:
        raise HTTPException(403, "Not your store")
    if new_price < float(store["supplier_cost"]) * 1.1:
        raise HTTPException(400, "Price too low")

    comm = round(new_price * COMMISSION_RATE, 2)
    margin = round(new_price - float(store["supplier_cost"]) - comm, 2)
    db.update_store(slug, {"seller_price": new_price, "commission": comm,
                            "margin": margin, "margin_pct": round((margin / new_price) * 100, 1)})
    return db.get_store(slug)


@app.put("/api/stores/{slug}/toggle")
async def toggle_store(slug: str, request: Request):
    body = await request.json()
    email = body.get("email", "")

    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found")
    if email and store.get("owner_email") != email:
        raise HTTPException(403, "Not your store")

    new_active = not store.get("active", True)
    db.update_store(slug, {"active": new_active})
    return {"active": new_active}


# ---------------------------------------------------------------------------
# Social Sharing
# ---------------------------------------------------------------------------
@app.get("/api/share/{slug}")
async def get_share_content(slug: str):
    store = db.get_store(slug)
    if not store:
        raise HTTPException(404, "Store not found")

    product = store.get("product_data", {})
    name = product.get("name", "Produit")
    price = float(store["seller_price"])
    url = f"{APP_URL}/s/{slug}"

    wa = f"🔥 {name} à seulement €{price:.2f} !\n\n✅ Livraison gratuite\n🔒 Paiement sécurisé\n\n👉 {url}"
    return {
        "platforms": {
            "whatsapp": {"caption": wa, "share_url": f"https://wa.me/?text={url_quote(wa)}"},
            "tiktok": {"caption": f"🔥 {name} — €{price:.2f}\n\n#bonplan #shopping #fyp"},
            "instagram": {"caption": f"✨ {name}\n💰 €{price:.2f}\n🔗 Lien en bio\n\n#bonplan #shopping"},
            "facebook": {"share_url": f"https://www.facebook.com/sharer/sharer.php?u={url_quote(url)}"},
        },
        "copy_link": url,
    }


# ---------------------------------------------------------------------------
# Seller Payment — Stripe Connect
# ---------------------------------------------------------------------------
@app.post("/api/seller/connect-stripe")
async def seller_connect_stripe(request: Request):
    """Create a Stripe Connect Express onboarding link for the seller."""
    body = await request.json()
    email = body.get("email", "")
    if not email:
        raise HTTPException(400, "Email required")

    user = db.get_user(email)
    if not user:
        raise HTTPException(404, "User not found")

    # Check if already has a Stripe account
    existing_id = user.get("stripe_account_id")
    if existing_id:
        # Create new login link for existing account
        try:
            link = stripe.AccountLink.create(
                account=existing_id,
                refresh_url=f"{APP_URL}/app?tab=profile&stripe=refresh",
                return_url=f"{APP_URL}/app?tab=profile&stripe=success",
                type="account_onboarding",
            )
            return {"onboarding_url": link.url, "account_id": existing_id}
        except stripe.StripeError:
            pass  # Account may be invalid, create new one

    # Create new Express account
    try:
        account = stripe.Account.create(
            type="express",
            country="FR",
            email=email,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            business_type="individual",
            metadata={"dropone_email": email},
        )
        db.update_seller_payment(email, {"stripe_account_id": account.id, "payout_method": "stripe"})

        link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=f"{APP_URL}/app?tab=profile&stripe=refresh",
            return_url=f"{APP_URL}/app?tab=profile&stripe=success",
            type="account_onboarding",
        )
        return {"onboarding_url": link.url, "account_id": account.id}
    except stripe.StripeError as e:
        raise HTTPException(400, f"Stripe error: {e}")


@app.get("/api/seller/stripe-status/{email}")
async def seller_stripe_status(email: str):
    """Check if seller's Stripe Connect account is ready."""
    user = db.get_user(email)
    if not user or not user.get("stripe_account_id"):
        return {"connected": False, "charges_enabled": False, "payouts_enabled": False}
    try:
        acct = stripe.Account.retrieve(user["stripe_account_id"])
        connected = acct.charges_enabled and acct.payouts_enabled
        if connected and user.get("payout_method") != "stripe":
            db.update_seller_payment(email, {"payout_method": "stripe"})
        return {
            "connected": connected,
            "charges_enabled": acct.charges_enabled,
            "payouts_enabled": acct.payouts_enabled,
            "account_id": user["stripe_account_id"],
        }
    except stripe.StripeError:
        return {"connected": False, "charges_enabled": False, "payouts_enabled": False}


@app.get("/api/seller/stripe-dashboard/{email}")
async def seller_stripe_dashboard(email: str):
    """Get a Stripe Express Dashboard login link for the seller."""
    user = db.get_user(email)
    if not user or not user.get("stripe_account_id"):
        raise HTTPException(404, "No Stripe account linked")
    try:
        link = stripe.Account.create_login_link(user["stripe_account_id"])
        return {"dashboard_url": link.url}
    except stripe.StripeError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------------------
# Seller Payment — PayPal
# ---------------------------------------------------------------------------
@app.post("/api/seller/set-paypal")
async def seller_set_paypal(request: Request):
    """Set seller's PayPal email for payouts."""
    body = await request.json()
    email = body.get("email", "")
    paypal_email = body.get("paypal_email", "")
    if not email or not paypal_email:
        raise HTTPException(400, "email and paypal_email required")
    if not EMAIL_RE.match(paypal_email):
        raise HTTPException(400, "Invalid PayPal email")

    user = db.get_user(email)
    if not user:
        raise HTTPException(404, "User not found")

    db.update_seller_payment(email, {
        "paypal_email": paypal_email.lower().strip(),
        "payout_method": "paypal" if not user.get("stripe_account_id") else user.get("payout_method", "paypal"),
    })
    return {"paypal_email": paypal_email, "payout_method": "paypal"}


# ---------------------------------------------------------------------------
# Seller Balance & Withdrawals
# ---------------------------------------------------------------------------
@app.get("/api/seller/balance/{email}")
async def seller_balance(email: str):
    """Get seller's current balance, payment method, and payout history."""
    user = db.get_user(email)
    if not user:
        return {"balance": 0, "total_earned": 0, "total_withdrawn": 0,
                "payout_method": None, "paypal_email": None, "stripe_connected": False}

    balance = round(float(user.get("balance") or user.get("total_earnings") or 0), 2)
    total_earned = round(float(user.get("total_earnings") or 0), 2)
    total_withdrawn = round(float(user.get("total_withdrawn") or 0), 2)

    return {
        "balance": balance,
        "total_earned": total_earned,
        "total_withdrawn": total_withdrawn,
        "payout_method": user.get("payout_method"),
        "paypal_email": user.get("paypal_email"),
        "stripe_connected": bool(user.get("stripe_account_id")),
        "min_withdrawal": 10.0,
    }


@app.post("/api/seller/withdraw")
async def seller_withdraw(request: Request):
    """Request a withdrawal. Minimum €10."""
    body = await request.json()
    email = body.get("email", "")
    amount = float(body.get("amount", 0))

    if not email:
        raise HTTPException(400, "Email required")
    if amount < 10:
        raise HTTPException(400, "Minimum withdrawal: €10")

    user = db.get_user(email)
    if not user:
        raise HTTPException(404, "User not found")

    balance = round(float(user.get("balance") or user.get("total_earnings") or 0), 2)
    if amount > balance:
        raise HTTPException(400, f"Insufficient balance (€{balance})")

    method = user.get("payout_method")
    if not method:
        raise HTTPException(400, "Configure your payment method first (Stripe or PayPal)")

    payout_id = f"PO-{uuid.uuid4().hex[:8].upper()}"
    payout_status = "pending"
    payout_error = ""

    # --- Stripe Connect Transfer ---
    if method == "stripe" and user.get("stripe_account_id"):
        try:
            transfer = stripe.Transfer.create(
                amount=int(amount * 100),
                currency="eur",
                destination=user["stripe_account_id"],
                description=f"DropOne payout {payout_id}",
                metadata={"email": email, "payout_id": payout_id},
            )
            payout_status = "completed"
            logger.info(f"Stripe transfer {transfer.id} → {email}: €{amount}")
        except stripe.StripeError as e:
            payout_status = "failed"
            payout_error = str(e)
            logger.error(f"Stripe payout failed: {e}")

    # --- PayPal Payout ---
    elif method == "paypal" and user.get("paypal_email"):
        try:
            import httpx as _hx
            token = await _get_paypal_token()
            async with _hx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{PAYPAL_BASE}/v1/payments/payouts",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={
                        "sender_batch_header": {
                            "sender_batch_id": payout_id,
                            "email_subject": "Votre paiement DropOne",
                            "email_message": f"Vous avez reçu €{amount:.2f} de vos ventes DropOne.",
                        },
                        "items": [{
                            "recipient_type": "EMAIL",
                            "amount": {"value": f"{amount:.2f}", "currency": "EUR"},
                            "receiver": user["paypal_email"],
                            "note": f"DropOne payout {payout_id}",
                            "sender_item_id": payout_id,
                        }],
                    },
                )
                resp.raise_for_status()
                payout_status = "completed"
                logger.info(f"PayPal payout → {user['paypal_email']}: €{amount}")
        except Exception as e:
            payout_status = "failed"
            payout_error = str(e)
            logger.error(f"PayPal payout failed: {e}")
    else:
        raise HTTPException(400, "Payment method not properly configured")

    # Record payout
    db.create_payout({
        "payout_id": payout_id, "email": email, "amount": amount,
        "method": method, "status": payout_status, "error": payout_error,
    })

    # Update balance
    if payout_status == "completed":
        new_balance = round(balance - amount, 2)
        new_withdrawn = round(float(user.get("total_withdrawn") or 0) + amount, 2)
        db.update_seller_payment(email, {"balance": new_balance, "total_withdrawn": new_withdrawn})

    if payout_status == "failed":
        raise HTTPException(500, f"Payout failed: {payout_error}")

    return {"payout_id": payout_id, "amount": amount, "method": method,
            "status": payout_status, "new_balance": round(balance - amount, 2)}


@app.get("/api/seller/payouts/{email}")
async def seller_payouts(email: str):
    """Get payout history for a seller."""
    return {"payouts": db.get_payouts(email)}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
