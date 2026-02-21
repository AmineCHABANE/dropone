"""
DropOne — AI Store Generator v3
Full French store pages, dynamic reviews, SEO meta, PayPal checkout.
"""

import re
import json
import random
import hashlib
import html as html_mod

STORE_PREFIXES = [
    "The", "My", "Shop", "Get", "Try", "Love", "Pure", "Vibe", "Glow",
    "Nova", "Luxe", "Peak", "Zen", "Aura", "Flow", "Edge", "Core",
]
STORE_SUFFIXES = [
    "Store", "Shop", "Hub", "Co", "Lab", "Zone", "Spot", "Box",
    "Den", "Nest", "Bay", "Kit", "Fix", "Pop",
]
EMOJIS = ["🛍️", "✨", "🔥", "💎", "🌟", "🚀", "💫", "⚡", "🎯", "💜", "🌿", "🎁"]
COLORS = [
    ("#6366f1", "#818cf8"), ("#8b5cf6", "#a78bfa"), ("#ec4899", "#f472b6"),
    ("#f43f5e", "#fb7185"), ("#f97316", "#fb923c"), ("#eab308", "#facc15"),
    ("#22c55e", "#4ade80"), ("#06b6d4", "#22d3ee"), ("#3b82f6", "#60a5fa"),
    ("#0ea5e9", "#38bdf8"),
]
SELLING_POINTS_FR = [
    "✅ Livraison gratuite dans le monde entier",
    "🔒 Paiement 100% sécurisé",
    "📦 Expédié sous 24h",
    "⭐ 4.8/5 — plus de 2 400 avis clients",
    "🎁 Idée cadeau parfaite",
    "💯 Satisfait ou remboursé sous 30 jours",
    "🌍 Plus de 10 000 clients satisfaits",
    "⚡ Stock limité — commandez maintenant",
]

# Dynamic French reviews pool
REVIEW_NAMES_FR = [
    "Marie L.", "Thomas D.", "Sophie B.", "Lucas M.", "Emma R.",
    "Julien P.", "Camille G.", "Hugo V.", "Léa F.", "Nathan C.",
    "Chloé T.", "Antoine S.", "Manon H.", "Raphaël K.", "Sarah N.",
    "Alexandre J.", "Julie W.", "Maxime A.", "Laura E.", "Théo Z.",
]
REVIEW_TEXTS_5STARS_FR = [
    "Excellent produit ! La qualité est vraiment au rendez-vous. Livraison rapide et emballage soigné. Je recommande à 100% !",
    "Très satisfait de mon achat. Exactement comme sur les photos. Je l'utilise tous les jours, c'est devenu indispensable.",
    "Super rapport qualité-prix. J'ai comparé avec d'autres sites et c'est ici le meilleur deal. Livré en 10 jours.",
    "Incroyable ! J'en ai commandé un deuxième pour offrir. Tout le monde me demande où je l'ai trouvé.",
    "Franchement bluffé par la qualité. Le design est top et ça fonctionne parfaitement. Merci !",
    "Commande reçue rapidement, produit conforme à la description. Je suis ravie de mon achat !",
    "J'hésitais mais je ne regrette pas du tout. Produit de qualité, bien emballé, livraison OK.",
    "Parfait ! C'est mon 3ème achat sur ce site. Toujours aussi fiable et rapide.",
]
REVIEW_TEXTS_4STARS_FR = [
    "Bon produit dans l'ensemble. La couleur est légèrement différente de la photo mais ça reste très bien.",
    "Très bien, livraison un peu longue (12 jours) mais le produit vaut le coup d'attendre.",
    "Satisfait de mon achat. Petit bémol sur l'emballage mais le produit est nickel.",
]
REVIEW_DATES_FR = [
    "Il y a 2 jours", "Il y a 3 jours", "Il y a 5 jours",
    "Il y a 1 semaine", "Il y a 1 semaine", "Il y a 2 semaines",
]


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug[:40].strip('-')


def _generate_fallback(product: dict, custom_name: str = None) -> dict:
    name = custom_name
    if not name:
        cat_words = {
            "tech": ["Tech","Gadget","Digital"], "home": ["Home","Living","Cozy"],
            "fashion": ["Style","Wear","Look"], "beauty": ["Glow","Beauty","Radiant"],
            "fitness": ["Fit","Active","Strong"], "pet": ["Pet","Paw","Buddy"],
            "kids": ["Little","Play","Fun"], "auto": ["Drive","Auto","Road"],
            "wellness": ["Zen","Calm","Well"],
        }
        mid = random.choice(cat_words.get(product.get("category", ""), ["Daily"]))
        name = f"{random.choice(STORE_PREFIXES)}{mid}{random.choice(STORE_SUFFIXES)}"
    colors = random.choice(COLORS)
    return {
        "name": name, "slug": _slugify(name),
        "tagline": f"Découvrez {product['name']} — offre limitée !",
        "logo_emoji": random.choice(EMOJIS),
        "color_primary": colors[0], "color_accent": colors[1],
        "product_description": product.get("short_desc", ""),
        "selling_points": random.sample(SELLING_POINTS_FR, 4),
    }


async def generate_store(product: dict, custom_name: str = None, ai_client=None) -> dict:
    if not ai_client:
        return _generate_fallback(product, custom_name)
    try:
        prompt = f"""Génère une identité de boutique dropshipping pour ce produit :
Produit : {product['name']}
Description : {product.get('short_desc', '')}
Catégorie : {product.get('category', 'general')}
Prix : €{product['suggested_price']}
{"Utilise ce nom de boutique : " + custom_name if custom_name else "Génère un nom de boutique accrocheur (2-3 mots max, brandable)."}
Réponds EN JSON uniquement, rien d'autre :
{{"name": "NomBoutique", "tagline": "Slogan accrocheur (max 8 mots)", "logo_emoji": "un seul emoji", "product_description": "Description produit convaincante en 2 phrases en français", "selling_points": ["point1", "point2", "point3", "point4"]}}"""

        response = ai_client.chat.completions.create(
            model="gpt-4o-mini", max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        data = json.loads(text)
        colors = random.choice(COLORS)
        return {
            "name": custom_name or data.get("name", "MaBoutique"),
            "slug": _slugify(custom_name or data.get("name", "maboutique")),
            "tagline": data.get("tagline", f"Découvrez {product['name']}"),
            "logo_emoji": data.get("logo_emoji", "🛍️"),
            "color_primary": colors[0], "color_accent": colors[1],
            "product_description": data.get("product_description", product.get("short_desc", "")),
            "selling_points": data.get("selling_points", random.sample(SELLING_POINTS_FR, 4)),
        }
    except Exception:
        return _generate_fallback(product, custom_name)


def _generate_reviews(seed: int) -> str:
    """Generate 3 unique French reviews based on store seed."""
    rng = random.Random(seed)
    names = rng.sample(REVIEW_NAMES_FR, 3)
    dates = rng.sample(REVIEW_DATES_FR, 3)
    
    # 2 five-star + 1 four-star
    texts_5 = rng.sample(REVIEW_TEXTS_5STARS_FR, 2)
    text_4 = rng.choice(REVIEW_TEXTS_4STARS_FR)
    
    reviews = []
    for i in range(3):
        stars = "★★★★★" if i < 2 else "★★★★☆"
        text = texts_5[i] if i < 2 else text_4
        reviews.append(f'''<div class="review">
<div class="review-header"><span class="review-name">{names[i]}</span><span class="review-date">{dates[i]}</span></div>
<div class="review-stars">{stars}</div>
<div class="review-text">{text}</div>
</div>''')
    return "\n".join(reviews)


# ---------------------------------------------------------------------------
# Generate customer-facing store HTML page — FULL FRENCH
# ---------------------------------------------------------------------------
def generate_store_page(store: dict, paypal_client_id: str = "") -> str:
    product = store["product"]
    price = float(store.get("seller_price", 0))
    old_price = round(price * 1.6, 2)
    color1 = store.get("color_primary", "#6366f1")
    color2 = store.get("color_accent", "#818cf8")
    emoji = store.get("logo_emoji", "🛍️")
    points = store.get("selling_points", SELLING_POINTS_FR[:4])
    if isinstance(points, str):
        try:
            points = json.loads(points)
        except Exception:
            points = SELLING_POINTS_FR[:4]
    image = product["images"][0] if product.get("images") else ""

    seed = int(hashlib.md5(store.get("slug", "x").encode()).hexdigest()[:8], 16)
    reviews_count = 1800 + (seed % 2400)
    rating = 4.6 + (seed % 4) * 0.1
    stock_left = 3 + (seed % 16)
    discount_pct = 20 + (seed % 31)

    safe_name = html_mod.escape(product.get('name', 'Produit'))
    safe_store = html_mod.escape(store.get('store_name', 'Boutique'))
    safe_tagline = html_mod.escape(store.get('tagline', ''))
    safe_desc = html_mod.escape(store.get('product_description', product.get('short_desc', '')))
    safe_image = html_mod.escape(image)
    slug = store.get("slug", "")

    points_html = "\n".join(f'<div class="sp">{html_mod.escape(str(p))}</div>' for p in points)
    reviews_html = _generate_reviews(seed)
    paypal_display = "block" if paypal_client_id else "none"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>{safe_name} — {safe_store}</title>
<meta name="description" content="{safe_tagline}">
<meta property="og:type" content="product">
<meta property="og:title" content="{safe_name} — {safe_store}">
<meta property="og:description" content="{safe_desc}">
<meta property="og:image" content="{safe_image}">
<meta property="og:url" content="/s/{slug}">
<meta property="product:price:amount" content="{price:.2f}">
<meta property="product:price:currency" content="EUR">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{safe_name}">
<meta name="twitter:description" content="{safe_tagline}">
<meta name="twitter:image" content="{safe_image}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{{--c1:{color1};--c2:{color2};--bg:#fff;--text:#1a1a2e;--text2:#4a4a6a;--text3:#8a8aa0;--card:#f8f9fc;--border:#e8e8f0;--green:#22c55e;--red:#ef4444;--orange:#f97316}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Plus Jakarta Sans',-apple-system,sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;overflow-x:hidden}}
.banner{{background:linear-gradient(135deg,var(--c1),var(--c2));color:#fff;text-align:center;padding:10px 16px;font-size:.8rem;font-weight:600;letter-spacing:.5px}}
.header{{padding:16px 20px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);position:sticky;top:0;background:rgba(255,255,255,.95);backdrop-filter:blur(10px);z-index:100}}
.store-logo{{font-size:1.1rem;font-weight:800;display:flex;align-items:center;gap:8px}}
.cart-icon{{width:36px;height:36px;border-radius:50%;background:var(--card);display:flex;align-items:center;justify-content:center;font-size:1.1rem}}
.product-image{{width:100%;aspect-ratio:1;object-fit:cover;background:var(--card)}}
.content{{padding:20px;max-width:480px;margin:0 auto}}
.rating{{display:flex;align-items:center;gap:8px;margin-bottom:12px}}
.stars{{color:#fbbf24;font-size:.9rem;letter-spacing:2px}}
.rating-text{{font-size:.8rem;color:var(--text3)}}
.product-title{{font-size:1.5rem;font-weight:800;line-height:1.3;margin-bottom:12px}}
.price-row{{display:flex;align-items:baseline;gap:12px;margin-bottom:8px}}
.price{{font-size:1.8rem;font-weight:800;color:var(--c1)}}
.old-price{{font-size:1rem;color:var(--text3);text-decoration:line-through}}
.save-badge{{font-size:.75rem;font-weight:700;background:rgba(239,68,68,.1);color:var(--red);padding:4px 10px;border-radius:100px}}
.stock-warning{{display:flex;align-items:center;gap:6px;font-size:.8rem;color:var(--orange);font-weight:600;margin-bottom:20px}}
.stock-dot{{width:8px;height:8px;border-radius:50%;background:var(--orange);animation:pulse 1.5s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.description{{font-size:.95rem;color:var(--text2);line-height:1.7;margin-bottom:24px}}
.selling-points{{margin-bottom:24px}}
.sp{{padding:10px 0;font-size:.9rem;font-weight:500;border-bottom:1px solid var(--border)}}
.sp:last-child{{border:none}}
.cta-section{{position:fixed;bottom:0;left:0;right:0;padding:16px 20px;background:rgba(255,255,255,.95);backdrop-filter:blur(10px);border-top:1px solid var(--border);z-index:100}}
.cta-btn{{width:100%;padding:16px;background:linear-gradient(135deg,var(--c1),var(--c2));color:#fff;border:none;border-radius:14px;font-family:inherit;font-size:1.05rem;font-weight:700;cursor:pointer;transition:all .2s;display:flex;align-items:center;justify-content:center;gap:8px;box-shadow:0 4px 20px rgba(0,0,0,.15)}}
.cta-btn:active{{transform:scale(.98)}}
.cta-btn:disabled{{opacity:.6;cursor:wait}}
.cta-paypal{{background:linear-gradient(135deg,#0070ba,#003087);margin-top:8px}}
.secure-text{{text-align:center;font-size:.72rem;color:var(--text3);margin-top:8px}}
.shipping-info{{background:var(--card);border-radius:12px;padding:16px;margin-bottom:24px}}
.ship-row{{display:flex;align-items:center;gap:10px;padding:8px 0;font-size:.85rem}}
.ship-icon{{font-size:1.1rem}}
.reviews-section{{margin:24px 0 100px;padding-top:24px;border-top:1px solid var(--border)}}
.reviews-title{{font-size:1.1rem;font-weight:700;margin-bottom:16px}}
.review{{background:var(--card);border-radius:12px;padding:16px;margin-bottom:12px}}
.review-header{{display:flex;justify-content:space-between;margin-bottom:8px}}
.review-name{{font-weight:600;font-size:.9rem}}
.review-date{{font-size:.75rem;color:var(--text3)}}
.review-stars{{color:#fbbf24;font-size:.8rem;margin-bottom:6px}}
.review-text{{font-size:.85rem;color:var(--text2);line-height:1.5}}
.bottom-spacer{{height:140px}}
.trust-badges{{display:flex;justify-content:center;gap:16px;margin:20px 0;flex-wrap:wrap}}
.trust-badge{{display:flex;align-items:center;gap:4px;font-size:.72rem;color:var(--text3);font-weight:500}}
@media(min-width:768px){{.content{{max-width:520px;padding:32px}}.product-image{{max-width:520px;margin:0 auto;display:block;border-radius:0 0 20px 20px}}}}
</style>
</head>
<body>
<div class="banner">🔥 VENTE FLASH — {discount_pct}% DE RÉDUCTION — Se termine ce soir !</div>
<div class="header">
  <div class="store-logo">{emoji} {safe_store}</div>
  <div class="cart-icon">🛒</div>
</div>
<img class="product-image" src="{safe_image}" alt="{safe_name}" onerror="this.style.background='linear-gradient(135deg,{color1}22,{color2}22)';this.style.minHeight='300px'">
<div class="content">
  <div class="rating"><span class="stars">★★★★★</span><span class="rating-text">{rating:.1f} ({reviews_count:,} avis)</span></div>
  <h1 class="product-title">{safe_name}</h1>
  <div class="price-row">
    <span class="price">€{price:.2f}</span>
    <span class="old-price">€{old_price:.2f}</span>
    <span class="save-badge">ÉCONOMISEZ €{old_price - price:.2f}</span>
  </div>
  <div class="stock-warning"><span class="stock-dot"></span>Plus que {stock_left} en stock — commandez maintenant !</div>
  <p class="description">{safe_desc}</p>
  <div class="selling-points">{points_html}</div>
  <div class="shipping-info">
    <div class="ship-row"><span class="ship-icon">🚚</span> Livraison express gratuite (7-14 jours ouvrés)</div>
    <div class="ship-row"><span class="ship-icon">🔄</span> Retours gratuits sous 30 jours</div>
    <div class="ship-row"><span class="ship-icon">🔒</span> Paiement sécurisé — Stripe & PayPal</div>
    <div class="ship-row"><span class="ship-icon">💬</span> Service client disponible 7j/7</div>
  </div>
  <div class="trust-badges">
    <div class="trust-badge">🔒 SSL 256-bit</div>
    <div class="trust-badge">✅ Vérifié</div>
    <div class="trust-badge">🌍 Livraison mondiale</div>
    <div class="trust-badge">↩️ Retours faciles</div>
  </div>
  <div class="reviews-section">
    <div class="reviews-title">Ce que nos clients disent</div>
    {reviews_html}
  </div>
  <div class="bottom-spacer"></div>
</div>
<div class="cta-section">
  <button class="cta-btn" onclick="checkout('stripe')" id="btnStripe">💳 Payer par carte — €{price:.2f}</button>
  <button class="cta-btn cta-paypal" onclick="checkout('paypal')" id="btnPaypal" style="display:{paypal_display}">🅿️ Payer avec PayPal — €{price:.2f}</button>
  <div class="secure-text">🔒 SSL 256-bit • Paiement sécurisé par Stripe & PayPal</div>
</div>
<script>
async function checkout(method) {{
  var btns = document.querySelectorAll('.cta-btn');
  btns.forEach(function(b) {{ b.disabled = true; b.textContent = '⏳ Chargement...'; }});
  try {{
    var res = await fetch('/api/checkout/create', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        store_slug: '{slug}',
        customer_name: '',
        customer_email: '',
        shipping_address: {{}},
        payment_method: method
      }})
    }});
    var data = await res.json();
    if (data.checkout_url) {{
      window.location.href = data.checkout_url;
    }} else {{
      alert('Le paiement est temporairement indisponible. Veuillez réessayer.');
    }}
  }} catch(e) {{
    alert('Erreur de connexion. Veuillez réessayer.');
  }}
  btns.forEach(function(b) {{ b.disabled = false; }});
  document.getElementById('btnStripe').innerHTML = '💳 Payer par carte — €{price:.2f}';
  document.getElementById('btnPaypal').innerHTML = '🅿️ Payer avec PayPal — €{price:.2f}';
}}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Success page — French
# ---------------------------------------------------------------------------
def generate_success_page(store: dict, product: dict) -> str:
    safe_name = html_mod.escape(product.get("name", "Produit"))
    safe_store = html_mod.escape(store.get("store_name", "Boutique"))
    color1 = store.get("color_primary", "#6366f1")
    color2 = store.get("color_accent", "#818cf8")
    emoji = store.get("logo_emoji", "🛍️")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Commande confirmée — {safe_store}</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Plus Jakarta Sans',-apple-system,sans-serif;background:#f8f9fc;color:#1a1a2e;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}}
.card{{background:#fff;border-radius:24px;padding:40px 32px;max-width:420px;width:100%;text-align:center;box-shadow:0 8px 40px rgba(0,0,0,.08)}}
.check{{width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,{color1},{color2});display:flex;align-items:center;justify-content:center;font-size:2.5rem;margin:0 auto 24px;animation:pop .5s ease}}
@keyframes pop{{0%{{transform:scale(0)}}50%{{transform:scale(1.2)}}100%{{transform:scale(1)}}}}
h1{{font-size:1.5rem;font-weight:800;margin-bottom:8px}}
.sub{{color:#4a4a6a;font-size:.9rem;line-height:1.6;margin-bottom:24px}}
.product{{display:flex;align-items:center;gap:12px;background:#f8f9fc;border-radius:12px;padding:12px;margin-bottom:24px;text-align:left}}
.product img{{width:60px;height:60px;border-radius:8px;object-fit:cover}}
.product-info{{flex:1}}
.product-info .name{{font-weight:700;font-size:.9rem}}
.product-info .email-note{{font-size:.78rem;color:#8a8aa0;margin-top:2px}}
.timeline{{text-align:left;margin:20px 0;padding:0 16px}}
.timeline-step{{display:flex;gap:12px;padding-bottom:16px;position:relative}}
.timeline-step:last-child{{padding-bottom:0}}
.timeline-dot{{width:24px;height:24px;min-width:24px;border-radius:50%;background:linear-gradient(135deg,{color1},{color2});display:flex;align-items:center;justify-content:center;font-size:.7rem;color:#fff}}
.timeline-step:not(:last-child)::after{{content:'';position:absolute;left:11px;top:28px;bottom:0;width:2px;background:#e8e8f0}}
.timeline-text{{font-size:.82rem;color:#4a4a6a;padding-top:3px}}
.timeline-text strong{{color:#1a1a2e;display:block;margin-bottom:2px}}
.btn{{display:inline-block;padding:14px 32px;background:linear-gradient(135deg,{color1},{color2});color:#fff;border-radius:14px;text-decoration:none;font-weight:700;font-size:.95rem}}
</style>
</head>
<body>
<div class="card">
  <div class="check">✓</div>
  <h1>Commande confirmée ! 🎉</h1>
  <p class="sub">Merci pour votre achat chez {emoji} {safe_store}.<br>Vous recevrez un email de confirmation sous peu.</p>
  <div class="product">
    <img src="{product.get('images', [''])[0]}" alt="" onerror="this.style.display='none'">
    <div class="product-info">
      <div class="name">{safe_name}</div>
      <div class="email-note">📧 Les infos de suivi seront envoyées par email</div>
    </div>
  </div>
  <div class="timeline">
    <div class="timeline-step">
      <div class="timeline-dot">✓</div>
      <div class="timeline-text"><strong>Commande reçue</strong>Votre commande est en cours de traitement</div>
    </div>
    <div class="timeline-step">
      <div class="timeline-dot">2</div>
      <div class="timeline-text"><strong>Préparation</strong>Votre colis est préparé sous 24-48h</div>
    </div>
    <div class="timeline-step">
      <div class="timeline-dot">3</div>
      <div class="timeline-text"><strong>Expédition</strong>Numéro de suivi envoyé par email</div>
    </div>
    <div class="timeline-step">
      <div class="timeline-dot">4</div>
      <div class="timeline-text"><strong>Livraison</strong>Réception sous 7-14 jours ouvrés</div>
    </div>
  </div>
  <a href="/s/{store.get('slug', '')}" class="btn">Continuer mes achats</a>
</div>
</body>
</html>"""
