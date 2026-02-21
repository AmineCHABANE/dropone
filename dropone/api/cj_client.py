"""
DropOne — CJ Dropshipping API Client
Handles: authentication, product search, order placement, tracking.
API docs: https://developers.cjdropshipping.cn/en/api/api2/
"""

import os
import json
import logging
import time
from typing import Optional, Dict, List

import httpx

logger = logging.getLogger("dropone.cj")

CJ_API_BASE = "https://developers.cjdropshipping.com/api2.0/v1"
CJ_API_KEY = os.getenv("CJ_API_KEY", "")

# Token cache (module-level)
_token_cache = {
    "access_token": "",
    "refresh_token": "",
    "expires_at": 0,
    "refresh_expires_at": 0,
}


# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------
async def _get_access_token() -> str:
    """Get valid access token, refreshing if needed."""
    now = time.time()

    if _token_cache["access_token"] and now < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    # Try refresh
    if _token_cache["refresh_token"] and now < _token_cache["refresh_expires_at"]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{CJ_API_BASE}/authentication/refreshAccessToken",
                    json={"refreshToken": _token_cache["refresh_token"]},
                )
                data = resp.json()
                if data.get("result"):
                    d = data["data"]
                    _token_cache["access_token"] = d["accessToken"]
                    _token_cache["refresh_token"] = d["refreshToken"]
                    _token_cache["expires_at"] = now + 14 * 86400 - 3600
                    _token_cache["refresh_expires_at"] = now + 179 * 86400
                    logger.info("CJ token refreshed")
                    return _token_cache["access_token"]
        except Exception as e:
            logger.warning(f"CJ refresh failed: {e}")

    # New token
    if not CJ_API_KEY:
        logger.error("CJ_API_KEY not set")
        return ""

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{CJ_API_BASE}/authentication/getAccessToken",
                json={"apiKey": CJ_API_KEY},
            )
            data = resp.json()
            if data.get("result"):
                d = data["data"]
                _token_cache["access_token"] = d["accessToken"]
                _token_cache["refresh_token"] = d["refreshToken"]
                _token_cache["expires_at"] = now + 14 * 86400 - 3600
                _token_cache["refresh_expires_at"] = now + 179 * 86400
                logger.info(f"CJ auth OK, openId={d.get('openId')}")
                return _token_cache["access_token"]
            else:
                logger.error(f"CJ auth failed: {data.get('message')}")
                return ""
    except Exception as e:
        logger.error(f"CJ auth error: {e}")
        return ""


async def _cj(method: str, endpoint: str, payload: dict = None, params: dict = None) -> dict:
    """Make authenticated CJ API request."""
    token = await _get_access_token()
    if not token:
        return {"result": False, "message": "No CJ token"}

    url = f"{CJ_API_BASE}/{endpoint}"
    headers = {"CJ-Access-Token": token, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers, params=params)
            elif method == "PATCH":
                resp = await client.patch(url, headers=headers, json=payload)
            else:
                resp = await client.post(url, headers=headers, json=payload)
            return resp.json()
    except Exception as e:
        logger.error(f"CJ {endpoint}: {e}")
        return {"result": False, "message": str(e)}


# ---------------------------------------------------------------------------
# PRODUCTS
# ---------------------------------------------------------------------------
async def search_products(keyword: str, page: int = 1, page_size: int = 20) -> List[Dict]:
    """Search CJ products."""
    data = await _cj("GET", "product/list", params={
        "productNameEn": keyword,
        "pageNum": page,
        "pageSize": page_size,
    })
    if data.get("result") and data.get("data"):
        return data["data"].get("list", [])
    return []


async def get_product(pid: str) -> Optional[Dict]:
    """Get product detail by CJ pid."""
    data = await _cj("GET", "product/query", params={"pid": pid})
    if data.get("result") and data.get("data"):
        return data["data"]
    return None


# ---------------------------------------------------------------------------
# ORDER PLACEMENT
# ---------------------------------------------------------------------------
async def place_order(
    vid: str,
    quantity: int,
    name: str,
    phone: str,
    country_code: str,
    province: str,
    city: str,
    address: str,
    zip_code: str,
    our_order_id: str,
) -> Dict:
    """Place a real order on CJ. Returns cj_order_id on success."""
    payload = {
        "orderNumber": our_order_id,
        "shippingZip": zip_code,
        "shippingCountryCode": country_code,
        "shippingCountry": country_code,
        "shippingProvince": province,
        "shippingCity": city,
        "shippingAddress": address,
        "shippingCustomerName": name,
        "shippingPhone": phone or "0000000000",
        "remark": f"DropOne {our_order_id}",
        "fromCountryCode": "",
        "logisticName": "",
        "products": [{"vid": vid, "quantity": quantity}],
    }

    logger.info(f"CJ order: {our_order_id}, vid={vid}")
    data = await _cj("POST", "shopping/order/createOrder", payload=payload)

    if data.get("result") and data.get("data"):
        oid = data["data"].get("orderId", "")
        logger.info(f"CJ order created: {oid}")
        return {"success": True, "cj_order_id": oid}
    return {"success": False, "error": data.get("message", "CJ error")}


async def confirm_order(cj_order_id: str) -> Dict:
    """Confirm/pay a CJ order after creation."""
    data = await _cj("PATCH", "shopping/order/confirmOrder", payload={"orderId": cj_order_id})
    if data.get("result"):
        logger.info(f"CJ order confirmed: {cj_order_id}")
        return {"success": True}
    return {"success": False, "error": data.get("message", "confirm error")}


# ---------------------------------------------------------------------------
# TRACKING
# ---------------------------------------------------------------------------
async def get_order_detail(cj_order_id: str) -> Optional[Dict]:
    """Get CJ order details."""
    data = await _cj("GET", "shopping/order/getOrderDetail", params={"orderId": cj_order_id})
    if data.get("result") and data.get("data"):
        return data["data"]
    return None


async def get_tracking(cj_order_id: str) -> Optional[Dict]:
    """Get tracking info."""
    order = await get_order_detail(cj_order_id)
    if order:
        return {
            "status": order.get("orderStatus", ""),
            "tracking_number": order.get("trackNumber", ""),
            "logistics": order.get("logisticName", ""),
        }
    return None


# ---------------------------------------------------------------------------
# SHIPPING ESTIMATE
# ---------------------------------------------------------------------------
async def shipping_estimate(vid: str, country_code: str, qty: int = 1) -> List[Dict]:
    """Get shipping options and costs."""
    data = await _cj("POST", "logistic/freightCalculate", payload={
        "startCountryCode": "",
        "endCountryCode": country_code,
        "products": [{"vid": vid, "quantity": qty}],
    })
    if data.get("result") and data.get("data"):
        return data["data"]
    return []


# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------
async def health() -> Dict:
    token = await _get_access_token()
    return {"connected": bool(token), "preview": (token[:8] + "...") if token else ""}
