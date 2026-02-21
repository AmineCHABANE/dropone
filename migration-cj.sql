-- ============================================================================
-- DropOne: COMPLETE Migration v3.2
-- Run this in Supabase SQL Editor
-- Fixes: missing stripe_account_id, payouts table, kv_cache, store_status
-- ============================================================================

-- ===== USERS: Add ALL missing columns =====
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_account_id TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS balance NUMERIC(10,2) DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_withdrawn NUMERIC(10,2) DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_method TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS paypal_email TEXT DEFAULT '';

-- Sync balance for existing users who earned before balance column existed
UPDATE users SET balance = COALESCE(total_earnings, 0) - COALESCE(total_withdrawn, 0)
WHERE balance = 0 AND COALESCE(total_earnings, 0) > 0;

-- ===== ORDERS: CJ tracking columns =====
ALTER TABLE orders ADD COLUMN IF NOT EXISTS supplier_order_id TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS tracking_number TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS logistics_name TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS error TEXT DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_orders_supplier_order_id ON orders(supplier_order_id) WHERE supplier_order_id != '';

-- ===== STORES: archival system =====
ALTER TABLE stores ADD COLUMN IF NOT EXISTS store_status TEXT DEFAULT 'active';
CREATE INDEX IF NOT EXISTS idx_stores_owner_status ON stores(owner_email, store_status);

-- ===== PAYOUTS TABLE (was completely missing!) =====
CREATE TABLE IF NOT EXISTS payouts (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    payout_id TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    method TEXT NOT NULL DEFAULT 'paypal',
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payouts_email ON payouts(email);
CREATE INDEX IF NOT EXISTS idx_payouts_created ON payouts(created_at DESC);

-- RLS for payouts
ALTER TABLE payouts ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
  CREATE POLICY "Service role full access" ON payouts FOR ALL USING (TRUE) WITH CHECK (TRUE);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ===== KV_CACHE (for catalog persistence) =====
CREATE TABLE IF NOT EXISTS kv_cache (
    id TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ===== SUPPORT TICKETS (basic customer support) =====
CREATE TABLE IF NOT EXISTS support_tickets (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    ticket_id TEXT UNIQUE NOT NULL,
    order_id TEXT,
    customer_email TEXT NOT NULL,
    seller_email TEXT,
    store_slug TEXT,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_order ON support_tickets(order_id);
CREATE INDEX IF NOT EXISTS idx_tickets_seller ON support_tickets(seller_email);

ALTER TABLE support_tickets ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
  CREATE POLICY "Service role full access" ON support_tickets FOR ALL USING (TRUE) WITH CHECK (TRUE);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- DONE — All missing tables and columns created!
-- ============================================================================
