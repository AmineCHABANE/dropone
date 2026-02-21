-- DropOne: Seller Payment System Migration
-- Run this in Supabase SQL Editor

-- 1. Add payment columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_account_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS paypal_email TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_method TEXT DEFAULT NULL;  -- 'stripe' or 'paypal'
ALTER TABLE users ADD COLUMN IF NOT EXISTS balance NUMERIC(10,2) DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_withdrawn NUMERIC(10,2) DEFAULT 0;

-- 2. Set balance = total_earnings for existing users
UPDATE users SET balance = total_earnings WHERE balance = 0 AND total_earnings > 0;

-- 3. Create payouts table
CREATE TABLE IF NOT EXISTS payouts (
    id BIGSERIAL PRIMARY KEY,
    payout_id TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    method TEXT NOT NULL,  -- 'stripe' or 'paypal'
    status TEXT DEFAULT 'pending',  -- pending, completed, failed
    error TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Enable RLS
ALTER TABLE payouts ENABLE ROW LEVEL SECURITY;

-- 5. Allow service role full access
CREATE POLICY "Service role full access on payouts"
    ON payouts FOR ALL
    USING (true)
    WITH CHECK (true);

-- 6. Index
CREATE INDEX IF NOT EXISTS idx_payouts_email ON payouts(email);
CREATE INDEX IF NOT EXISTS idx_payouts_status ON payouts(status);
CREATE INDEX IF NOT EXISTS idx_users_stripe_account ON users(stripe_account_id) WHERE stripe_account_id IS NOT NULL;
