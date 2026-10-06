BEGIN;

-- Add per-second rate columns to rate_cards if they don't exist
ALTER TABLE rate_cards
ADD COLUMN IF NOT EXISTS in_rate_per_sec NUMERIC(14,8) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS ob_rate_per_sec NUMERIC(14,8) DEFAULT NULL;

-- Populate existing rows by calculating from per-minute rates
UPDATE rate_cards
SET 
  in_rate_per_sec = in_rate_per_min / 60.0,
  ob_rate_per_sec = ob_rate_per_min / 60.0
WHERE in_rate_per_sec IS NULL OR ob_rate_per_sec IS NULL;

-- Add constraints safely
ALTER TABLE rate_cards DROP CONSTRAINT IF EXISTS rate_cards_in_rate_per_sec_check;
ALTER TABLE rate_cards DROP CONSTRAINT IF EXISTS rate_cards_ob_rate_per_sec_check;

ALTER TABLE rate_cards
ADD CONSTRAINT rate_cards_in_rate_per_sec_check CHECK (in_rate_per_sec >= 0),
ADD CONSTRAINT rate_cards_ob_rate_per_sec_check CHECK (ob_rate_per_sec >= 0);

-- Make columns NOT NULL after population
ALTER TABLE rate_cards
ALTER COLUMN in_rate_per_sec SET NOT NULL,
ALTER COLUMN ob_rate_per_sec SET NOT NULL;

COMMIT;