"""
DropOne — CJ Dropshipping API Client
Full integration with CJ Dropshipping API v2.0
Handles: auth, product search, order creation, payment, tracking.

Setup:
1. Go to cjdropshipping.com → create account
2. My CJ → Authorization → Stores → API → Generate API Key
3. Put CJ_API_EMAIL and CJ_API_KEY in .env

Docs: https://developers.cjdropshipping.com/
"""

import os
import time
import httpx
import logging
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger("dropone.cj")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CJ_BASE_URL = "https://developers.cjdropshipping.com/api2.0/v1"

# Token cache
_token_cache = {"token": "", "expires_at": 0}


def _get_credentials() -> tuple[str, str]:
    """Read CJ credentials from env at call time (supports .env loading)."""
    email = os.getenv("CJ_API_EMAIL", "")
    key = os.getenv("CJ_API_KEY", "")
    return email, key


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class CJProduct:
    pid: str
    name: str
    sku: str
    image: str
    sell_price: float
    category: str
    variants: list = field(default_factory=list)
    description: str = ""
    weight: float = 0
    packing_weight: float = 0
    shipping_time: str = ""


@dataclass
class CJOrder:
    cj_order_id: str
    order_number: str
    status: str
    tracking_number: str = ""
    logistics_name: str = ""


@dataclass
class CJShippingEstimate:
    logistics_name: str
    price: float
    delivery_days_min: int
    delivery_days_max: int


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
async def get_access_token() -> str:
    """
    Get CJ access token. Tokens last 24h, cached in memory.
    
    API: POST /authentication/getAccessToken
    Body: { "email": "xxx", "password": "xxx" }  ← password = API key
    """
    global _token_cache

    # Return cached token if still valid (with 1h buffer)
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 3600:
        return _token_cache["token"]

    email, api_key = _get_credentials()
    if not email or not api_key:
        raise CJError("CJ_API_EMAIL and CJ_API_KEY must be set in .env")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{CJ_BASE_URL}/authentication/getAccessToken",
            json={
                "email": email,
                "password": api_key,
            },
        )
        data = resp.json()

    if not data.get("result"):
        raise CJError(f"Auth failed: {data.get('message', 'Unknown error')}")

    token = data["data"]["accessToken"]
    # Token valid for ~24h
    _token_cache["token"] = token
    _token_cache["expires_at"] = time.time() + 86400

    logger.info("CJ access token refreshed")
    return token


async def _headers() -> dict:
    """Build auth headers for CJ API calls."""
    token = await get_access_token()
    return {
        "CJ-Access-Token": token,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
async def search_products(
    query: str = "",
    category_id: str = "",
    page: int = 1,
    page_size: int = 20,
    country_code: str = "FR",
) -> list[CJProduct]:
    """
    Search CJ product catalog.
    
    API: GET /product/list
    Params: productNameEn, categoryId, pageNum, pageSize, countryCode
    """
    headers = await _headers()
    params = {
        "pageNum": page,
        "pageSize": page_size,
    }
    if query:
        params["productNameEn"] = query
    if category_id:
        params["categoryId"] = category_id
    if country_code:
        params["countryCode"] = country_code

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{CJ_BASE_URL}/product/list",
            headers=headers,
            params=params,
        )
        data = resp.json()

    if not data.get("result"):
        logger.warning(f"CJ product search failed: {data.get('message')}")
        return []

    products = []
    for item in data.get("data", {}).get("list", []):
        products.append(CJProduct(
            pid=item.get("pid", ""),
            name=item.get("productNameEn", ""),
            sku=item.get("productSku", ""),
            image=item.get("productImage", ""),
            sell_price=float(item.get("sellPrice", 0)),
            category=item.get("categoryName", ""),
            description=item.get("description", ""),
        ))

    return products


async def get_product_detail(pid: str) -> Optional[CJProduct]:
    """
    Get detailed product info including variants.
    
    API: GET /product/query?pid=xxx
    """
    headers = await _headers()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{CJ_BASE_URL}/product/query",
            headers=headers,
            params={"pid": pid},
        )
        data = resp.json()

    if not data.get("result") or not data.get("data"):
        return None

    item = data["data"]
    variants = []
    for v in item.get("variants", []):
        variants.append({
            "vid": v.get("vid", ""),
            "name": v.get("variantNameEn", ""),
            "sku": v.get("variantSku", ""),
            "price": float(v.get("variantSellPrice", 0)),
            "image": v.get("variantImage", ""),
            "stock": v.get("variantVolume", 0),
        })

    return CJProduct(
        pid=item.get("pid", ""),
        name=item.get("productNameEn", ""),
        sku=item.get("productSku", ""),
        image=item.get("productImage", ""),
        sell_price=float(item.get("sellPrice", 0)),
        category=item.get("categoryName", ""),
        variants=variants,
        description=item.get("description", ""),
        weight=float(item.get("productWeight", 0)),
        packing_weight=float(item.get("packingWeight", 0)),
    )


async def get_categories() -> list[dict]:
    """
    Get all CJ product categories.
    
    API: GET /product/getCategory
    """
    headers = await _headers()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{CJ_BASE_URL}/product/getCategory",
            headers=headers,
        )
        data = resp.json()

    if not data.get("result"):
        return []

    return data.get("data", [])


# ---------------------------------------------------------------------------
# Shipping
# ---------------------------------------------------------------------------
async def get_shipping_estimate(
    pid: str,
    vid: str,
    country_code: str = "FR",
    quantity: int = 1,
) -> list[CJShippingEstimate]:
    """
    Get shipping cost and delivery time estimates.
    
    API: POST /logistic/freightCalculate
    """
    headers = await _headers()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{CJ_BASE_URL}/logistic/freightCalculate",
            headers=headers,
            json={
                "startCountryCode": "CN",
                "endCountryCode": country_code,
                "products": [{
                    "quantity": quantity,
                    "vid": vid,
                }],
            },
        )
        data = resp.json()

    if not data.get("result"):
        return []

    estimates = []
    for item in data.get("data", []):
        # Parse delivery days — API returns string "7-15" or int or None
        aging = str(item.get("logisticAging", "7-15"))
        try:
            if "-" in aging:
                parts = aging.split("-")
                days_min, days_max = int(parts[0]), int(parts[-1])
            else:
                days_min = days_max = int(aging) if aging.isdigit() else 10
        except (ValueError, IndexError):
            days_min, days_max = 7, 15

        estimates.append(CJShippingEstimate(
            logistics_name=item.get("logisticName", ""),
            price=float(item.get("logisticPrice", 0)),
            delivery_days_min=days_min,
            delivery_days_max=days_max,
        ))

    return sorted(estimates, key=lambda e: e.price)


# ---------------------------------------------------------------------------
# Orders — THE CORE
# ---------------------------------------------------------------------------
async def create_order(
    order_number: str,
    product_vid: str,
    quantity: int,
    customer_name: str,
    customer_email: str,
    shipping_address: str,
    shipping_address2: str = "",
    shipping_city: str = "",
    shipping_province: str = "",
    shipping_zip: str = "",
    shipping_country_code: str = "FR",
    shipping_country: str = "France",
    shipping_phone: str = "",
    house_number: str = "",
    logistics_name: str = "",
    from_country_code: str = "CN",
    pay_type: int = 2,  # 2 = auto pay with CJ balance, 3 = manual pay
    remark: str = "DropOne order",
) -> CJOrder:
    """
    Create an order on CJ Dropshipping.
    This is the main fulfillment function.
    
    API: POST /shopping/order/createOrderV2
    
    payType:
      2 = Auto pay with CJ wallet balance (recommended)
      3 = Manual pay later
      
    Flow:
      1. Order created on CJ
      2. If payType=2, CJ debits your wallet automatically
      3. CJ picks, packs, and ships
      4. Tracking number assigned → webhook notification
      5. Customer receives package
    """
    headers = await _headers()

    payload = {
        "orderNumber": order_number,
        "shippingZip": shipping_zip,
        "shippingCountry": shipping_country,
        "shippingCountryCode": shipping_country_code,
        "shippingProvince": shipping_province,
        "shippingCity": shipping_city,
        "shippingPhone": shipping_phone or "0000000000",
        "shippingCustomerName": customer_name,
        "shippingAddress": shipping_address,
        "shippingAddress2": shipping_address2,
        "email": customer_email,
        "remark": remark,
        "logisticName": logistics_name,
        "fromCountryCode": from_country_code,
        "houseNumber": house_number,
        "payType": str(pay_type),
        "products": [
            {
                "vid": product_vid,
                "quantity": quantity,
            }
        ],
    }

    logger.info(f"Creating CJ order: {order_number} → {shipping_country_code}")

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{CJ_BASE_URL}/shopping/order/createOrderV2",
            headers=headers,
            json=payload,
        )
        data = resp.json()

    if not data.get("result"):
        error_msg = data.get("message", "Unknown CJ error")
        logger.error(f"CJ order creation failed: {error_msg}")
        raise CJError(f"Order creation failed: {error_msg}")

    order_data = data.get("data", {})

    cj_order = CJOrder(
        cj_order_id=str(order_data.get("orderId", "")),
        order_number=order_number,
        status="created",
    )

    logger.info(f"CJ order created: {cj_order.cj_order_id}")
    return cj_order


async def get_order_status(order_id: str) -> Optional[dict]:
    """
    Query order status and tracking info.
    
    API: GET /shopping/order/getOrderDetail?orderId=xxx
    """
    headers = await _headers()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{CJ_BASE_URL}/shopping/order/getOrderDetail",
            headers=headers,
            params={"orderId": order_id},
        )
        data = resp.json()

    if not data.get("result"):
        return None

    order = data.get("data", {})
    return {
        "cj_order_id": order.get("orderId", ""),
        "order_number": order.get("orderNum", ""),
        "status": order.get("orderStatus", ""),
        "tracking_number": order.get("trackNumber", ""),
        "logistics_name": order.get("logisticName", ""),
        "shipping_status": order.get("shippingStatus", ""),
        "create_date": order.get("createDate", ""),
        "pay_date": order.get("payDate", ""),
    }


async def list_orders(
    page: int = 1,
    page_size: int = 20,
    status: str = "",
) -> list[dict]:
    """
    List all CJ orders.
    
    API: GET /shopping/order/list
    """
    headers = await _headers()
    params = {"pageNum": page, "pageSize": page_size}
    if status:
        params["orderStatus"] = status

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{CJ_BASE_URL}/shopping/order/list",
            headers=headers,
            params=params,
        )
        data = resp.json()

    if not data.get("result"):
        return []

    return data.get("data", {}).get("list", [])


async def confirm_order(order_id: str) -> bool:
    """
    Confirm an order for processing.
    
    API: PATCH /shopping/order/confirmOrder
    """
    headers = await _headers()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"{CJ_BASE_URL}/shopping/order/confirmOrder",
            headers=headers,
            json={"orderId": order_id},
        )
        data = resp.json()

    return data.get("result", False)


# ---------------------------------------------------------------------------
# Payment / Balance
# ---------------------------------------------------------------------------
async def get_balance() -> dict:
    """
    Check CJ wallet balance.
    
    API: GET /shopping/pay/getBalance
    """
    headers = await _headers()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{CJ_BASE_URL}/shopping/pay/getBalance",
            headers=headers,
        )
        data = resp.json()

    if not data.get("result"):
        return {"balance": 0, "currency": "USD"}

    balance_data = data.get("data", {})
    return {
        "balance": float(balance_data.get("amount", 0)),
        "currency": balance_data.get("currency", "USD"),
    }


# ---------------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------------
async def get_tracking(tracking_number: str) -> list[dict]:
    """
    Get tracking events for a shipment.
    
    API: GET /logistic/getTrackInfo?trackNumber=xxx
    """
    headers = await _headers()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{CJ_BASE_URL}/logistic/getTrackInfo",
            headers=headers,
            params={"trackNumber": tracking_number},
        )
        data = resp.json()

    if not data.get("result"):
        return []

    return data.get("data", {}).get("trackInfo", [])


# ---------------------------------------------------------------------------
# Webhook Processing
# ---------------------------------------------------------------------------
def process_cj_webhook(payload: dict) -> dict:
    """
    Process incoming CJ webhook notifications.
    
    CJ sends webhooks for:
    - Order status changes
    - Tracking number assigned
    - Delivery confirmation
    
    Setup: In CJ dashboard → Settings → Webhook → add your URL:
    https://dropone.app/api/webhook/cj
    """
    event_type = payload.get("type", "")
    data = payload.get("data", {})

    if event_type == "ORDER_STATUS_CHANGE":
        return {
            "event": "status_change",
            "order_id": data.get("orderId", ""),
            "order_number": data.get("orderNum", ""),
            "old_status": data.get("oldStatus", ""),
            "new_status": data.get("newStatus", ""),
        }

    elif event_type == "TRACKING_NUMBER_UPDATE":
        return {
            "event": "tracking_update",
            "order_id": data.get("orderId", ""),
            "order_number": data.get("orderNum", ""),
            "tracking_number": data.get("trackNumber", ""),
            "logistics_name": data.get("logisticName", ""),
        }

    elif event_type == "ORDER_DELIVERED":
        return {
            "event": "delivered",
            "order_id": data.get("orderId", ""),
            "order_number": data.get("orderNum", ""),
        }

    return {"event": "unknown", "raw": payload}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class CJError(Exception):
    """CJ API error."""
    pass


# ---------------------------------------------------------------------------
# Health check — verify CJ connection
# ---------------------------------------------------------------------------
async def check_connection() -> dict:
    """Test CJ API connection and return account status."""
    try:
        token = await get_access_token()
        balance = await get_balance()
        return {
            "connected": True,
            "balance": balance["balance"],
            "currency": balance["currency"],
            "token_preview": token[:8] + "...",
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }
