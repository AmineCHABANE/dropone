"""
DropOne — Multi-Product Store Builder
Generates themed collections: "Ambiance Bedroom" = Projector + Neon + Lamp
Doubles average order value by cross-selling related products.

Features:
- AI-generated themed collections
- Smart product pairing based on category + price range
- Collection landing pages with multiple products
- Upsell/cross-sell on checkout
"""

import random
import logging
from typing import Optional
from catalog import PRODUCTS, get_product

logger = logging.getLogger("dropone.multistore")


# ---------------------------------------------------------------------------
# Pre-defined collections (curated bundles)
# ---------------------------------------------------------------------------
COLLECTIONS = [
    {
        "id": "bedroom-vibes",
        "name": "🌙 Bedroom Vibes",
        "tagline": "Transforme ta chambre en espace cozy",
        "product_ids": ["home-004", "home-001", "tech-001", "home-003"],
        "color": "#6366f1",
        "emoji": "🌙",
        "category_focus": "home",
    },
    {
        "id": "self-care-kit",
        "name": "✨ Self-Care Kit",
        "tagline": "Ta routine beauté complète",
        "product_ids": ["beauty-001", "beauty-002", "beauty-003", "premium-002"],
        "color": "#ec4899",
        "emoji": "✨",
        "category_focus": "beauty",
    },
    {
        "id": "tech-essentials",
        "name": "📱 Tech Essentials",
        "tagline": "Les gadgets que tout le monde veut",
        "product_ids": ["tech-004", "tech-002", "tech-003", "premium-001"],
        "color": "#3b82f6",
        "emoji": "📱",
        "category_focus": "tech",
    },
    {
        "id": "fitness-starter",
        "name": "💪 Fitness Starter Pack",
        "tagline": "Tout pour commencer ta transformation",
        "product_ids": ["fit-001", "fit-002", "fit-003"],
        "color": "#22c55e",
        "emoji": "💪",
        "category_focus": "fitness",
    },
    {
        "id": "gift-box",
        "name": "🎁 Gift Box",
        "tagline": "Les meilleures idées cadeaux",
        "product_ids": ["home-002", "fashion-001", "home-004", "home-003"],
        "color": "#f97316",
        "emoji": "🎁",
        "category_focus": "gift",
    },
    {
        "id": "pet-paradise",
        "name": "🐾 Pet Paradise",
        "tagline": "Ton animal va t'adorer",
        "product_ids": ["pet-001", "pet-002"],
        "color": "#eab308",
        "emoji": "🐾",
        "category_focus": "pet",
    },
]


def get_collections() -> list[dict]:
    """Get all available themed collections with full product data."""
    result = []
    for col in COLLECTIONS:
        products = []
        total_cost = 0
        total_suggested = 0
        for pid in col["product_ids"]:
            p = get_product(pid)
            if p:
                products.append(p)
                total_cost += p["cost"]
                total_suggested += p["suggested_price"]

        if len(products) < 2:
            continue

        # Bundle discount: 10% off combined price
        bundle_price = round(total_suggested * 0.9, 2)
        savings = round(total_suggested - bundle_price, 2)
        avg_margin = round((1 - total_cost / bundle_price) * 100, 1) if bundle_price > 0 else 0

        result.append({
            "id": col["id"],
            "name": col["name"],
            "tagline": col["tagline"],
            "emoji": col["emoji"],
            "color": col["color"],
            "products": products,
            "product_count": len(products),
            "bundle_price": bundle_price,
            "original_price": round(total_suggested, 2),
            "savings": savings,
            "total_cost": round(total_cost, 2),
            "margin_pct": avg_margin,
        })

    return result


def get_collection(collection_id: str) -> Optional[dict]:
    """Get a specific collection by ID."""
    for col in get_collections():
        if col["id"] == collection_id:
            return col
    return None


def suggest_upsells(product_id: str, limit: int = 3) -> list[dict]:
    """
    Suggest related products for cross-selling.
    Called on the store page: "Complète ton achat avec..."
    """
    current = get_product(product_id)
    if not current:
        return []

    current_cat = current["category"]
    current_price = current["suggested_price"]

    # Score all other products
    candidates = []
    for p in PRODUCTS:
        if p["id"] == product_id:
            continue

        score = 0
        # Same category = strong match
        if p["category"] == current_cat:
            score += 30
        # Similar price range = good complement
        price_ratio = min(p["suggested_price"], current_price) / max(p["suggested_price"], current_price)
        score += price_ratio * 20
        # Trending products preferred
        score += p.get("trending_score", 50) * 0.3
        # Complementary categories
        complements = {
            "tech": ["home", "auto"],
            "home": ["tech", "wellness"],
            "beauty": ["wellness", "fitness"],
            "fitness": ["wellness", "beauty"],
            "fashion": ["beauty", "tech"],
            "pet": ["home"],
            "wellness": ["beauty", "fitness", "home"],
        }
        if p["category"] in complements.get(current_cat, []):
            score += 15

        candidates.append({**p, "_upsell_score": score})

    candidates.sort(key=lambda x: x["_upsell_score"], reverse=True)

    # Return top candidates without internal score
    result = []
    for c in candidates[:limit]:
        r = {k: v for k, v in c.items() if k != "_upsell_score"}
        result.append(r)
    return result


async def generate_collection_with_ai(
    theme: str,
    ai_client=None,
    budget_max: float = 200,
) -> Optional[dict]:
    """
    AI generates a custom themed collection.
    User says: "Crée une collection ambiance japonaise" → AI picks products + branding.
    """
    if not ai_client:
        return None

    product_list = "\n".join([
        f"- {p['id']}: {p['name']} (€{p['suggested_price']}, cat: {p['category']}) — {p['short_desc']}"
        for p in PRODUCTS
    ])

    try:
        prompt = f"""Tu es un expert en curation de produits e-commerce.
L'utilisateur veut créer une collection thématique: "{theme}"
Budget max client: €{budget_max}

Voici les produits disponibles:
{product_list}

Choisis 3-5 produits qui forment une collection cohérente autour du thème "{theme}".
Réponds en JSON uniquement:
{{
  "name": "Nom de la collection avec emoji",
  "tagline": "Slogan accrocheur en 1 ligne",
  "product_ids": ["id1", "id2", "id3"],
  "color": "#hex color qui correspond au thème",
  "explanation": "Pourquoi ces produits vont bien ensemble (1 phrase)"
}}"""

        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        import json
        data = json.loads(text)

        # Build full collection
        products = [get_product(pid) for pid in data.get("product_ids", []) if get_product(pid)]
        if len(products) < 2:
            return None

        total_price = sum(p["suggested_price"] for p in products)
        total_cost = sum(p["cost"] for p in products)
        bundle_price = round(total_price * 0.9, 2)

        return {
            "id": f"ai-{theme.lower().replace(' ', '-')[:20]}",
            "name": data.get("name", f"✨ {theme}"),
            "tagline": data.get("tagline", theme),
            "emoji": data.get("name", "✨")[0] if data.get("name") else "✨",
            "color": data.get("color", "#6366f1"),
            "products": products,
            "product_count": len(products),
            "bundle_price": bundle_price,
            "original_price": round(total_price, 2),
            "savings": round(total_price - bundle_price, 2),
            "total_cost": round(total_cost, 2),
            "margin_pct": round((1 - total_cost / bundle_price) * 100, 1),
            "explanation": data.get("explanation", ""),
            "ai_generated": True,
        }

    except Exception as e:
        logger.warning(f"AI collection generation failed: {e}")
        return None
