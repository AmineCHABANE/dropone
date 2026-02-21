-- ============================================================================
-- DropOne — Supabase Schema
-- Run this in Supabase SQL Editor (supabase.com → SQL Editor → New Query)
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- USERS
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    total_earnings NUMERIC(10,2) DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    badges JSONB DEFAULT '[]'::jsonb,
    streak_days INTEGER DEFAULT 0,
    last_sale_date DATE,
    paypal_email TEXT,
    stripe_customer_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

-- ============================================================================
-- STORES
-- ============================================================================
CREATE TABLE IF NOT EXISTS stores (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    store_id TEXT UNIQUE NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    owner_email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
    store_name TEXT NOT NULL,
    tagline TEXT,
    logo_emoji TEXT DEFAULT '🛒',
    color_primary TEXT DEFAULT '#6366f1',
    color_accent TEXT DEFAULT '#ec4899',
    product_id TEXT NOT NULL,
    product_data JSONB NOT NULL,          -- full product snapshot
    product_description TEXT,
    selling_points JSONB DEFAULT '[]'::jsonb,
    seller_price NUMERIC(10,2) NOT NULL,
    supplier_cost NUMERIC(10,2) NOT NULL,
    commission NUMERIC(10,2) NOT NULL,
    margin NUMERIC(10,2) NOT NULL,
    margin_pct NUMERIC(5,1) NOT NULL,
    total_sales INTEGER DEFAULT 0,
    total_revenue NUMERIC(10,2) DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    collection_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stores_slug ON stores(slug);
CREATE INDEX idx_stores_owner ON stores(owner_email);
CREATE INDEX idx_stores_product ON stores(product_id);
CREATE INDEX idx_stores_active ON stores(active) WHERE active = TRUE;

-- ============================================================================
-- ORDERS
-- ============================================================================
CREATE TABLE IF NOT EXISTS orders (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    order_id TEXT UNIQUE NOT NULL,
    store_slug TEXT NOT NULL REFERENCES stores(slug),
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    customer_email TEXT,                     -- can be null for some PayPal orders
    customer_name TEXT,
    shipping_address JSONB,
    amount_paid NUMERIC(10,2) NOT NULL,
    supplier_cost NUMERIC(10,2) NOT NULL,
    commission NUMERIC(10,2) NOT NULL,
    seller_margin NUMERIC(10,2) NOT NULL,
    status TEXT DEFAULT 'pending',         -- pending, processing, shipped, delivered, refunded, error
    payment_provider TEXT DEFAULT 'stripe', -- stripe, paypal
    payment_session_id TEXT,
    paypal_order_id TEXT,
    supplier_order_id TEXT,
    tracking_number TEXT,
    tracking_url TEXT,
    carrier TEXT,
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_orders_store ON orders(store_slug);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created ON orders(created_at DESC);

-- ============================================================================
-- ANALYTICS — Page Views
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_views (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    store_slug TEXT NOT NULL,
    ip_hash TEXT,                           -- hashed for privacy
    user_agent TEXT,
    referrer TEXT,
    source TEXT DEFAULT 'direct',           -- tiktok, instagram, facebook, google, direct
    device TEXT DEFAULT 'unknown',          -- mobile, desktop, tablet
    country TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_views_store ON analytics_views(store_slug);
CREATE INDEX idx_views_created ON analytics_views(created_at DESC);
CREATE INDEX idx_views_source ON analytics_views(source);

-- Partition hint: for high volume, consider partitioning by month
-- CREATE INDEX idx_views_store_date ON analytics_views(store_slug, created_at DESC);

-- ============================================================================
-- ANALYTICS — Conversions
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_conversions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    store_slug TEXT NOT NULL,
    order_id TEXT NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conv_store ON analytics_conversions(store_slug);

-- ============================================================================
-- PUSH SUBSCRIPTIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    email TEXT NOT NULL,
    subscription JSONB NOT NULL,           -- Web Push subscription object
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_push_email ON push_subscriptions(email);

-- ============================================================================
-- SELLER NETWORK — Sales (for collective intelligence)
-- ============================================================================
CREATE TABLE IF NOT EXISTS network_sales (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    product_id TEXT NOT NULL,
    product_name TEXT,
    category TEXT,
    amount NUMERIC(10,2) NOT NULL,
    seller_email TEXT NOT NULL,
    source TEXT DEFAULT 'direct',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_network_product ON network_sales(product_id);
CREATE INDEX idx_network_created ON network_sales(created_at DESC);

-- ============================================================================
-- NETWORK — Product view counter (aggregated)
-- ============================================================================
CREATE TABLE IF NOT EXISTS network_product_stats (
    product_id TEXT PRIMARY KEY,
    product_name TEXT,
    category TEXT,
    total_views INTEGER DEFAULT 0,
    total_sales INTEGER DEFAULT 0,
    total_revenue NUMERIC(10,2) DEFAULT 0,
    stores_count INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- HELPER: Auto-update updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_stores_updated BEFORE UPDATE ON stores FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_orders_updated BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- VIEWS — Dashboard aggregations
-- ============================================================================

-- Store analytics view
CREATE OR REPLACE VIEW store_analytics AS
SELECT
    s.slug,
    s.store_name,
    s.owner_email,
    s.seller_price,
    s.margin,
    s.total_sales,
    s.total_revenue,
    s.active,
    COALESCE(v.view_count, 0) AS total_views,
    COALESCE(v.views_today, 0) AS views_today,
    COALESCE(v.views_7d, 0) AS views_7d,
    CASE WHEN COALESCE(v.view_count, 0) > 0
         THEN ROUND(s.total_sales::numeric / v.view_count * 100, 2)
         ELSE 0
    END AS conversion_rate
FROM stores s
LEFT JOIN (
    SELECT
        store_slug,
        COUNT(*) AS view_count,
        COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 day') AS views_today,
        COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') AS views_7d
    FROM analytics_views
    GROUP BY store_slug
) v ON s.slug = v.store_slug;

-- Network trending view
CREATE OR REPLACE VIEW network_trending AS
SELECT
    ns.product_id,
    ns.product_name,
    ns.category,
    COUNT(*) AS sales_7d,
    SUM(ns.amount) AS revenue_7d,
    nps.total_views,
    nps.stores_count,
    CASE WHEN COALESCE(nps.total_views, 0) > 0
         THEN ROUND(COUNT(*)::numeric / nps.total_views * 100, 2)
         ELSE 0
    END AS conversion_rate
FROM network_sales ns
LEFT JOIN network_product_stats nps ON ns.product_id = nps.product_id
WHERE ns.created_at >= NOW() - INTERVAL '7 days'
GROUP BY ns.product_id, ns.product_name, ns.category, nps.total_views, nps.stores_count
ORDER BY sales_7d DESC;

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) — Supabase best practice
-- ============================================================================
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_views ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_conversions ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_sales ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_product_stats ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS (our backend uses service role key)
-- These policies allow the service role full access
CREATE POLICY "Service role full access" ON users FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON stores FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON orders FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON analytics_views FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON analytics_conversions FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON push_subscriptions FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON network_sales FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON network_product_stats FOR ALL USING (TRUE) WITH CHECK (TRUE);

-- ============================================================================
-- DONE — Your schema is ready!
-- ============================================================================
