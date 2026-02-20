-- DropOne: CJ Dropshipping Integration Migration
-- Run this in Supabase SQL Editor

-- Add supplier tracking columns to orders
ALTER TABLE orders ADD COLUMN IF NOT EXISTS supplier_order_id TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS tracking_number TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS logistics_name TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS error TEXT DEFAULT '';

-- Index for CJ order lookups
CREATE INDEX IF NOT EXISTS idx_orders_supplier_order_id ON orders(supplier_order_id) WHERE supplier_order_id != '';
