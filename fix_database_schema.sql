-- Fix missing columns in res_partner table
-- These columns are from AUTO-008 and AUTO-009 features

ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS registration_status VARCHAR;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS days_to_expiry INTEGER;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS last_expiry_alert_sent VARCHAR;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS performance_score NUMERIC;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS on_time_delivery_rate NUMERIC;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS dsr_rejection_rate NUMERIC;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS complaint_count INTEGER DEFAULT 0;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS total_pos_count INTEGER DEFAULT 0;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS performance_rating VARCHAR;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS last_score_update TIMESTAMP;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS registration_expiry_date DATE;
