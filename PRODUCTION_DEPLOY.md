# DropOne — Production Deployment Guide

## Architecture

```
Vercel (frontend + API)        Supabase (database)        Stripe + PayPal (payments)
┌─────────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  frontend/           │       │  PostgreSQL       │       │  Stripe Checkout │
│    index.html        │ ───→  │  + RLS           │       │  PayPal Orders   │
│    sw.js             │       │  + Views          │       │  Webhooks        │
│  api/                │       │  + Triggers       │       └──────────────────┘
│    index.py (FastAPI)│ ───→  │                   │
│    database.py       │       └──────────────────┘
│    store_generator.py│       
│    content_ai.py     │       OpenAI (AI)
│    ...               │       ┌──────────────────┐
└─────────────────────┘       │  GPT-4o-mini     │
                               │  Store generation │
                               │  Content creation │
                               └──────────────────┘
```

---

## Step 1 — Supabase Setup

1. Go to [supabase.com](https://supabase.com) → **New Project**
2. Choose a name (e.g., `dropone`) and a strong password
3. Wait for project creation (~2 min)
4. Go to **SQL Editor** → **New Query**
5. Paste the contents of `supabase_schema.sql` → **Run**
6. Go to **Settings → API**:
   - Copy **Project URL** → `SUPABASE_URL`
   - Copy **service_role key** (not anon!) → `SUPABASE_SERVICE_KEY`

---

## Step 2 — Stripe Setup

1. Go to [dashboard.stripe.com](https://dashboard.stripe.com)
2. **Developers → API Keys**:
   - Copy **Secret key** → `STRIPE_SECRET_KEY`
3. **Developers → Webhooks → Add endpoint**:
   - URL: `https://your-app.vercel.app/api/webhook/stripe`
   - Events: `checkout.session.completed`
   - Copy **Signing secret** → `STRIPE_WEBHOOK_SECRET`

---

## Step 3 — PayPal Setup

1. Go to [developer.paypal.com](https://developer.paypal.com)
2. **My Apps & Credentials → Create App**
3. Copy **Client ID** → `PAYPAL_CLIENT_ID`
4. Copy **Secret** → `PAYPAL_CLIENT_SECRET`
5. For testing: `PAYPAL_MODE=sandbox`
6. For production: `PAYPAL_MODE=live`

---

## Step 4 — OpenAI Setup

1. Go to [platform.openai.com](https://platform.openai.com)
2. **API Keys → Create new secret key**
3. Copy → `OPENAI_API_KEY`
4. The app uses `gpt-4o-mini` (cheap: ~$0.15/1M tokens)

---

## Step 5 — Deploy to Vercel

### Option A: One-click (recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# In the dropone/ directory
cd dropone
vercel

# Follow prompts:
# - Link to existing project? → No
# - Project name? → dropone
# - Framework? → Other
# - Build command? → (leave empty)
# - Output directory? → (leave empty)
```

### Option B: GitHub auto-deploy

1. Push to GitHub:
```bash
cd dropone
git init
git add .
git commit -m "DropOne v2 — production"
git remote add origin https://github.com/YOU/dropone.git
git push -u origin main
```

2. Go to [vercel.com](https://vercel.com) → **Import Project** → Select repo

### Set Environment Variables

In Vercel dashboard → **Settings → Environment Variables**, add ALL of these:

| Variable | Value |
|---|---|
| `OPENAI_API_KEY` | `sk-proj-...` |
| `STRIPE_SECRET_KEY` | `sk_live_...` or `sk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |
| `PAYPAL_CLIENT_ID` | `AX...` |
| `PAYPAL_CLIENT_SECRET` | `EL...` |
| `PAYPAL_MODE` | `sandbox` or `live` |
| `SUPABASE_URL` | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | `eyJ...` |
| `APP_URL` | `https://dropone.vercel.app` |

Then redeploy:
```bash
vercel --prod
```

---

## Step 6 — Custom Domain (Optional)

1. Vercel → **Settings → Domains** → Add `dropone.app` (or your domain)
2. Update DNS records as shown
3. Update `APP_URL` env var to match
4. Update Stripe webhook URL
5. Redeploy

---

## Step 7 — Go Live Checklist

- [ ] Supabase schema executed (tables created)
- [ ] All env vars set in Vercel
- [ ] Stripe webhook URL updated to production
- [ ] PayPal mode set to `live`
- [ ] `APP_URL` matches your actual domain
- [ ] Test: create a store
- [ ] Test: Stripe checkout (use test card 4242 4242 4242 4242)
- [ ] Test: PayPal checkout (sandbox account)
- [ ] Test: webhook receives payment → order created in Supabase
- [ ] Check Supabase → Table Editor → stores/orders have data

---

## Architecture Details

### Cost Estimate (per month)

| Service | Free Tier | Paid |
|---|---|---|
| Vercel | 100GB bandwidth, 100h compute | $20/mo Pro |
| Supabase | 500MB DB, 1GB storage | $25/mo Pro |
| OpenAI | Pay-per-use (~$0.15/1M tokens) | ~$5-20/mo |
| Stripe | 2.9% + €0.30 per transaction | — |
| PayPal | 2.9% + €0.35 per transaction | — |

**Total at start: ~$0/month** (all free tiers)
**At scale (1000 orders/mo): ~$50-70/month**

### File Structure

```
dropone/
├── api/                     # Vercel serverless backend
│   ├── index.py             # FastAPI app (main)
│   ├── database.py          # Supabase layer
│   ├── store_generator.py   # AI store + page generation
│   ├── content_ai.py        # Marketing content generator
│   ├── multi_store.py       # Collections engine
│   ├── catalog.py           # Product catalog
│   ├── notifications.py     # Push notifications
│   └── cj_client.py         # CJ Dropshipping API
├── frontend/                # Static files
│   ├── index.html           # PWA app (2000+ lines)
│   ├── sw.js                # Service worker
│   ├── manifest.json        # PWA manifest
│   └── nginx.conf           # (not used on Vercel)
├── vercel.json              # Vercel routing config
├── requirements.txt         # Python dependencies
├── supabase_schema.sql      # Database schema
├── .env.example             # Environment template
└── PRODUCTION_DEPLOY.md     # This file
```
