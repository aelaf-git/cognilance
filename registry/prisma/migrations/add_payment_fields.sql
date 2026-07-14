-- Additive columns for payout pricing (SQLite).
-- Applied automatically by `prisma db push` when using the project Prisma client.
-- Manual fallback if the registry DB already exists:
--   sqlite3 prisma/dev.db < prisma/migrations/add_payment_fields.sql

ALTER TABLE agents ADD COLUMN payout_wallet TEXT;
ALTER TABLE agents ADD COLUMN price_usd_cents INTEGER NOT NULL DEFAULT 0;
