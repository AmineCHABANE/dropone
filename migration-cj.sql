-- DropOne: Full Audit Migration v3.1
-- Run this in Supabase SQL Editor

-- ===== ORDERS: CJ tracking =====
ALTER TABLE orders ADD COLUMN IF NOT EXISTS supplier_order_id TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS tracking_number TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS logistics_name TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS error TEXT DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_orders_supplier_order_id ON orders(supplier_order_id) WHERE supplier_order_id != '';

-- ===== STORES: archival system =====
ALTER TABLE stores ADD COLUMN IF NOT EXISTS store_status TEXT DEFAULT 'active';
CREATE INDEX IF NOT EXISTS idx_stores_owner_status ON stores(owner_email, store_status);

-- ===== USERS: balance accounting =====
-- Ensure balance column exists (separate from total_earnings)
ALTER TABLE users ADD COLUMN IF NOT EXISTS balance NUMERIC DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_withdrawn NUMERIC DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_method TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS paypal_email TEXT DEFAULT '';

-- Sync balance for existing users who earned before balance column existed
UPDATE users SET balance = COALESCE(total_earnings, 0) - COALESCE(total_withdrawn, 0)
WHERE balance = 0 AND COALESCE(total_earnings, 0) > 0;

-- ===== CATALOG: persistent cache =====
CREATE TABLE IF NOT EXISTS kv_cache (
    id TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ===== CLEANUP: auto-delete soft-deleted stores after 30 days =====
-- (Optional cron — run manually or via pg_cron if available)
-- DELETE FROM stores WHERE store_status = 'deleted' AND created_at < NOW() - INTERVAL '30 days';
