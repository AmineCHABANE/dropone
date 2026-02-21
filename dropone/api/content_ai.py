"""
DropOne — AI Content Generator
Generates platform-optimized marketing content for sellers.
The #1 problem in dropshipping: sellers don't know HOW to sell.
This solves it by giving them ready-to-use content.

Features:
- TikTok video scripts (hook → demo → CTA)
- Instagram captions + story sequences
- Ad copy for paid campaigns (TikTok Ads, FB Ads)
- Posting schedule optimized per platform
- A/B test variants
"""

import os
import json
import random
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("dropone.content")


# ---------------------------------------------------------------------------
# Content templates (used as fallback when AI unavailable)
# ---------------------------------------------------------------------------
TIKTOK_HOOKS = [
    "Wait till you see this... 👀",
    "I can't believe this only costs €{price}",
    "POV: you just found the best {category} product of 2026",
    "This is the viral product everyone's talking about 🔥",
    "Stop scrolling — you NEED this",
    "I found the {category} product TikTok made me buy",
    "My room before vs after this product ✨",
    "3 reasons why everyone's buying this right now",
    "This €{price} product looks like it costs 10x more",
    "The product that broke the internet this week 👇",
]

TIKTOK_CTAS = [
    "Link in bio → don't miss out 🔗",
    "Comment 'LINK' and I'll DM you 📩",
    "Tap the link before it sells out ⚡",
    "🔗 in bio — limited stock!",
    "Follow + save for later 📌",
]

INSTAGRAM_HOOKS = [
    "The {category} game-changer you didn't know you needed 👆",
    "€{price} and worth every cent — here's why 👇",
    "My honest review after using this for a week:",
    "The product that's been going viral — and I see why ✨",
    "Swipe to see the before/after →",
]

BEST_POSTING_TIMES = {
    "tiktok": {
        "best_times": ["7h-9h", "12h-13h", "19h-22h"],
        "best_days": ["mardi", "jeudi", "samedi"],
        "tip": "Publie 1-3 vidéos/jour. La régularité compte plus que la perfection.",
    },
    "instagram": {
        "best_times": ["7h-9h", "12h-14h", "17h-19h"],
        "best_days": ["lundi", "mercredi", "vendredi"],
        "tip": "1 Reel + 3 Stories/jour. Utilise les stickers pour l'engagement.",
    },
    "facebook": {
        "best_times": ["9h-10h", "13h-14h", "19h-21h"],
        "best_days": ["mercredi", "vendredi", "dimanche"],
        "tip": "Poste dans les groupes thématiques. Pas de spam — apporte de la valeur.",
    },
    "snapchat": {
        "best_times": ["11h-13h", "20h-23h"],
        "best_days": ["samedi", "dimanche"],
        "tip": "Stories authentiques > contenu léché. Montre le produit en vrai.",
    },
}


# ---------------------------------------------------------------------------
# AI Content Generation
# ---------------------------------------------------------------------------
async def generate_content(
    product: dict,
    store: dict,
    platform: str,
    content_type: str = "organic",  # organic, ad, story
    ai_client=None,
    language: str = "fr",
) -> dict:
    """
    Generate marketing content for a specific platform.
    
    Returns:
    {
        "platform": "tiktok",
        "content_type": "organic",
        "scripts": [ {variant_a}, {variant_b} ],
        "hashtags": [...],
        "posting_schedule": {...},
        "tips": [...]
    }
    """
    store_url = store.get("url", f"https://dropone.app/s/{store.get('slug', '')}")
    product_name = product.get("name", "Produit")
    price = store.get("seller_price", product.get("suggested_price", 29.99))
    category = product.get("category", "general")
    desc = product.get("short_desc", "")

    if ai_client:
        try:
            return await _generate_with_ai(
                ai_client, product_name, price, category, desc,
                store_url, platform, content_type, language,
            )
        except Exception as e:
            logger.warning(f"AI content generation failed: {e}")

    # Fallback: template-based generation
    return _generate_from_templates(
        product_name, price, category, desc,
        store_url, platform, content_type,
    )


async def _generate_with_ai(
    ai_client, name, price, category, desc,
    store_url, platform, content_type, language,
) -> dict:
    """Use Claude to generate high-quality marketing content."""

    lang_instruction = "Réponds entièrement en français." if language == "fr" else "Respond in English."

    prompt = f"""{lang_instruction}

Tu es un expert en marketing digital et en création de contenu viral pour le dropshipping.
Génère du contenu marketing pour cette plateforme: {platform}
Type: {content_type} (organic = post gratuit, ad = publicité payante, story = story/reel)

PRODUIT:
- Nom: {name}
- Prix: €{price:.2f}
- Catégorie: {category}
- Description: {desc}
- Lien: {store_url}

Génère EXACTEMENT ce JSON, rien d'autre:
{{
  "scripts": [
    {{
      "label": "Variante A — [style en 2-3 mots]",
      "hook": "Phrase d'accroche (les 3 premières secondes, crucial)",
      "body": "Corps du contenu (adapté à {platform})",
      "cta": "Call to action final",
      "duration": "durée recommandée en secondes",
      "music_style": "type de musique/son recommandé"
    }},
    {{
      "label": "Variante B — [style différent]",
      "hook": "Accroche alternative",
      "body": "Corps alternatif",
      "cta": "CTA alternatif",
      "duration": "durée",
      "music_style": "musique"
    }}
  ],
  "hashtags": ["hashtag1", "hashtag2", "...10 hashtags max"],
  "tips": [
    "Conseil pratique 1 pour maximiser l'engagement",
    "Conseil pratique 2",
    "Conseil pratique 3"
  ],
  "shooting_guide": {{
    "setup": "Comment filmer (angle, lumière, décor)",
    "sequence": ["Plan 1: ...", "Plan 2: ...", "Plan 3: ..."],
    "props_needed": "Accessoires/décor recommandés",
    "editing_style": "Style de montage recommandé"
  }}
}}"""

    response = ai_client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    data = json.loads(text)

    # Add platform-specific metadata
    data["platform"] = platform
    data["content_type"] = content_type
    data["posting_schedule"] = BEST_POSTING_TIMES.get(platform, {})
    data["store_url"] = store_url

    return data


def _generate_from_templates(name, price, category, desc, store_url, platform, content_type) -> dict:
    """Generate content from templates when AI is unavailable."""

    cat_fr = {
        "tech": "tech", "home": "déco", "fashion": "mode",
        "beauty": "beauté", "fitness": "fitness", "pet": "animaux",
        "kids": "enfants", "auto": "auto", "wellness": "bien-être",
    }.get(category, "lifestyle")

    if platform == "tiktok":
        scripts = [
            {
                "label": "Variante A — Unboxing réaction",
                "hook": random.choice(TIKTOK_HOOKS).format(price=f"{price:.0f}", category=cat_fr),
                "body": f"[Montre le produit en gros plan]\n"
                        f"C'est le {name} et honnêtement, pour €{price:.2f} c'est dingue.\n"
                        f"{desc}\n"
                        f"[Montre-le en action / avant-après]",
                "cta": random.choice(TIKTOK_CTAS),
                "duration": "15-30 sec",
                "music_style": "Trending sound / upbeat lo-fi",
            },
            {
                "label": "Variante B — POV storytelling",
                "hook": f"POV: tu découvres le meilleur produit {cat_fr} de 2026 🤯",
                "body": f"[Face caméra, enthousiaste]\n"
                        f"Ok donc j'ai trouvé CE truc — le {name}\n"
                        f"Et franchement à €{price:.2f} c'est cadeau.\n"
                        f"[Démo rapide du produit]\n"
                        f"Regardez la qualité 👀",
                "cta": f"Lien en bio pour commander 🔗 Stock limité !",
                "duration": "20-45 sec",
                "music_style": "Voiceover + trending audio en fond",
            },
        ]
        hashtags = [
            "#fyp", "#pourtoi", "#bonplan", "#dropshipping",
            f"#{cat_fr}", "#trending", "#musthave", "#viral",
            "#tiktokmademebuyit", "#shopping",
        ]
    elif platform == "instagram":
        scripts = [
            {
                "label": "Variante A — Reel showcase",
                "hook": random.choice(INSTAGRAM_HOOKS).format(price=f"{price:.0f}", category=cat_fr),
                "body": f"✨ {name}\n\n"
                        f"💰 Seulement €{price:.2f}\n"
                        f"{desc}\n\n"
                        f"✅ Livraison gratuite\n"
                        f"🔒 Paiement 100% sécurisé\n"
                        f"📦 Reçu en 7-14 jours\n\n"
                        f"👉 Lien en bio pour commander !",
                "cta": "Double-tap si tu veux ❤️ + lien en bio",
                "duration": "15-30 sec",
                "music_style": "Trending Reel audio",
            },
            {
                "label": "Variante B — Carousel/Story",
                "hook": f"Slide 1: {name} — le produit viral du moment 🔥",
                "body": f"Slide 2: Pourquoi tout le monde l'achète ?\n"
                        f"→ {desc}\n\n"
                        f"Slide 3: Seulement €{price:.2f} (au lieu de €{price*1.6:.2f})\n\n"
                        f"Slide 4: Livraison gratuite + garantie 30 jours\n\n"
                        f"Slide 5: Commande maintenant 👇",
                "cta": "Lien en bio 🔗",
                "duration": "5 slides / 15 sec story",
                "music_style": "Chill / aesthetic",
            },
        ]
        hashtags = [
            "#instagood", "#bonplan", "#shopping", "#promo",
            f"#{cat_fr}", "#idéecadeau", "#trendy",
            "#instashopping", "#musthave", "#trouvaille",
        ]
    elif platform == "facebook":
        scripts = [
            {
                "label": "Variante A — Post groupe",
                "hook": f"🔥 Quelqu'un connaît le {name} ?",
                "body": f"Je viens de découvrir ce produit et honnêtement c'est top.\n\n"
                        f"{desc}\n\n"
                        f"C'est à €{price:.2f} seulement, livraison gratuite.\n"
                        f"J'ai commandé il y a 10 jours, reçu nickel.\n\n"
                        f"Le lien si ça vous intéresse : {store_url}",
                "cta": "Commenter si vous voulez le lien en MP !",
                "duration": "Post texte",
                "music_style": "N/A",
            },
            {
                "label": "Variante B — Ad copy",
                "hook": f"😱 -40% sur le {name} — derniers jours !",
                "body": f"⚡ OFFRE FLASH\n\n"
                        f"{name}\n"
                        f"✅ {desc}\n"
                        f"✅ Livraison GRATUITE en France\n"
                        f"✅ Paiement 100% sécurisé\n\n"
                        f"💰 €{price:.2f} au lieu de €{price*1.6:.2f}\n\n"
                        f"👉 Commander ici : {store_url}\n\n"
                        f"⏰ Stock limité — ne rate pas !",
                "cta": f"Commander maintenant → {store_url}",
                "duration": "Post/Ad",
                "music_style": "N/A",
            },
        ]
        hashtags = ["#bonplan", "#promo", "#offre", f"#{cat_fr}", "#shopping"]
    else:
        # Generic for other platforms
        scripts = [
            {
                "label": "Variante A — Message direct",
                "hook": f"Hey ! Regarde ce que j'ai trouvé 👀",
                "body": f"{name} à seulement €{price:.2f}\n{desc}\n{store_url}",
                "cta": "Dis-moi ce que t'en penses !",
                "duration": "Message",
                "music_style": "N/A",
            },
        ]
        hashtags = []

    tips = _get_platform_tips(platform, category)

    return {
        "platform": platform,
        "content_type": content_type,
        "scripts": scripts,
        "hashtags": hashtags,
        "posting_schedule": BEST_POSTING_TIMES.get(platform, {}),
        "tips": tips,
        "shooting_guide": _get_shooting_guide(platform, category),
        "store_url": store_url,
    }


def _get_platform_tips(platform: str, category: str) -> list[str]:
    """Platform-specific tips for maximum engagement."""
    base_tips = {
        "tiktok": [
            "Les 3 premières secondes décident si la vidéo sera virale — soigne l'accroche",
            "Filme en vertical (9:16), lumière naturelle, et parle à la caméra",
            "Publie entre 19h et 22h pour maximiser la portée en France",
            "Utilise les sons trending — TikTok pousse les vidéos avec des sons populaires",
            "Réponds à chaque commentaire pour booster l'engagement",
        ],
        "instagram": [
            "Utilise 5-10 hashtags pertinents max (pas 30 — l'algo pénalise)",
            "Poste ton Reel et mets le lien en bio juste après",
            "Ajoute des stickers interactifs dans tes Stories (sondage, question)",
            "Partage ton Reel en Story pour doubler la portée",
            "Collabore avec 2-3 micro-influenceurs dans ta niche",
        ],
        "facebook": [
            "Poste dans les groupes thématiques, pas en spam — raconte ton expérience",
            "Les posts avec photos/vidéos personnelles marchent 3x mieux",
            "Marketplace est gratuit et très efficace pour les produits physiques",
            "Réponds vite aux commentaires — FB récompense les conversations",
        ],
        "snapchat": [
            "Montre le produit en situation réelle, pas de mise en scène parfaite",
            "Utilise les filtres et les lenses pour rendre le contenu fun",
            "Snap directement à tes contacts proches — le bouche-à-oreille marche",
        ],
    }
    return base_tips.get(platform, ["Sois authentique et montre le produit en vrai"])


def _get_shooting_guide(platform: str, category: str) -> dict:
    """How to shoot content for this product."""
    guides = {
        "tech": {
            "setup": "Fond neutre sombre, lumière LED latérale, gros plans",
            "sequence": [
                "Plan 1: Unboxing — ouvre le colis face caméra",
                "Plan 2: Gros plan du produit — montre les détails",
                "Plan 3: Démo en action — allume/utilise le produit",
                "Plan 4: Réaction — montre ta surprise/satisfaction",
            ],
            "props_needed": "Fond noir ou bureau clean, bonne lumière",
            "editing_style": "Cuts rapides, zoom transitions, musique upbeat",
        },
        "home": {
            "setup": "Chambre/salon avec lumière chaude, ambiance cozy",
            "sequence": [
                "Plan 1: Avant — ta pièce 'avant' le produit",
                "Plan 2: Installation — montre la mise en place",
                "Plan 3: Révélation — le résultat final, éteins les lumières si LED",
                "Plan 4: Ambiance — plan large de l'atmosphère créée",
            ],
            "props_needed": "Pièce rangée, lumière tamisée pour l'ambiance",
            "editing_style": "Transition lente avant/après, musique chill/lo-fi",
        },
        "beauty": {
            "setup": "Miroir ring light, visage bien éclairé, fond neutre",
            "sequence": [
                "Plan 1: Ton visage 'avant' utilisation",
                "Plan 2: Application/utilisation du produit",
                "Plan 3: Résultat — zoom sur la différence",
                "Plan 4: Verdict — ton avis face caméra",
            ],
            "props_needed": "Ring light, miroir, serviette/accessoires",
            "editing_style": "Split-screen avant/après, musique relaxante",
        },
    }

    return guides.get(category, {
        "setup": "Lumière naturelle, fond propre, smartphone en mode portrait",
        "sequence": [
            "Plan 1: Hook — accroche visuelle ou textuelle",
            "Plan 2: Présentation — montre le produit sous tous les angles",
            "Plan 3: Démo — utilise-le en temps réel",
            "Plan 4: CTA — dis aux gens où acheter",
        ],
        "props_needed": "Bonne lumière + smartphone + trépied/support",
        "editing_style": "Coupes dynamiques, texte overlay, musique trending",
    })


# ---------------------------------------------------------------------------
# Ad Budget Calculator
# ---------------------------------------------------------------------------
def calculate_ad_budget(
    product_price: float,
    supplier_cost: float,
    commission_rate: float = 0.08,
    target_roas: float = 3.0,
) -> dict:
    """
    Calculate recommended ad budget based on margins.
    
    ROAS (Return On Ad Spend) = Revenue / Ad Cost
    Break-even ROAS = Price / (Price - Cost - Commission - Stripe fees)
    """
    stripe_fee = product_price * 0.029 + 0.30  # Stripe 2.9% + 30¢
    commission = product_price * commission_rate
    net_margin = product_price - supplier_cost - commission - stripe_fee

    if net_margin <= 0:
        return {
            "viable": False,
            "message": "Marge trop faible pour de la pub payante. Augmente ton prix.",
        }

    breakeven_cpa = net_margin  # Max cost per acquisition to break even
    target_cpa = net_margin / target_roas  # Target CPA for profitability

    return {
        "viable": True,
        "net_margin": round(net_margin, 2),
        "breakeven_cpa": round(breakeven_cpa, 2),
        "target_cpa": round(target_cpa, 2),
        "daily_budgets": {
            "test": {"budget": 5, "expected_sales": round(5 / target_cpa, 1) if target_cpa > 0 else 0,
                     "label": "🧪 Test (€5/jour)"},
            "scale": {"budget": 20, "expected_sales": round(20 / target_cpa, 1) if target_cpa > 0 else 0,
                      "label": "📈 Scale (€20/jour)"},
            "aggressive": {"budget": 50, "expected_sales": round(50 / target_cpa, 1) if target_cpa > 0 else 0,
                           "label": "🚀 Agressif (€50/jour)"},
        },
        "recommendations": [
            f"Ta marge nette par vente : €{net_margin:.2f}",
            f"CPA max pour être rentable : €{breakeven_cpa:.2f}",
            f"CPA cible (ROAS x{target_roas:.0f}) : €{target_cpa:.2f}",
            "Commence toujours par €5/jour pendant 3-5 jours pour tester",
            "Si CPA < €{:.2f} après 50 clics → scale à €20/jour".format(target_cpa),
            "Arrête une pub après €15 dépensés sans vente",
        ],
    }
