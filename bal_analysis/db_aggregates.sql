-- New Aggregate Tables for Dashboard Analytics

CREATE TABLE IF NOT EXISTS cdr_metrics_day (
    customer_id TEXT NOT NULL,
    bucket_day DATE NOT NULL,
    direction TEXT NOT NULL,
    total_calls BIGINT NOT NULL DEFAULT 0,
    answered_calls BIGINT NOT NULL DEFAULT 0,
    missed_calls BIGINT NOT NULL DEFAULT 0,
    total_duration_sec BIGINT NOT NULL DEFAULT 0,
    total_billsec BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (customer_id, bucket_day, direction)
);

CREATE TABLE IF NOT EXISTS cdr_metrics_hourly (
    customer_id TEXT NOT NULL,
    bucket_hour TIMESTAMPTZ NOT NULL,
    direction TEXT NOT NULL,
    total_calls BIGINT NOT NULL DEFAULT 0,
    answered_calls BIGINT NOT NULL DEFAULT 0,
    missed_calls BIGINT NOT NULL DEFAULT 0,
    total_duration_sec BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (customer_id, bucket_hour, direction)
);

CREATE TABLE IF NOT EXISTS cdr_metrics_did_day (
    customer_id TEXT NOT NULL,
    bucket_day DATE NOT NULL,
    did_value TEXT NOT NULL,
    inbound_calls BIGINT NOT NULL DEFAULT 0,
    answered_calls BIGINT NOT NULL DEFAULT 0,
    missed_calls BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (customer_id, bucket_day, did_value)
);

CREATE TABLE IF NOT EXISTS cdr_metrics_hour_of_day (
    customer_id TEXT NOT NULL,
    hour_of_day SMALLINT NOT NULL CHECK (hour_of_day >= 0 AND hour_of_day <= 23),
    direction TEXT NOT NULL,
    total_calls BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (customer_id, hour_of_day, direction)
);

CREATE TABLE IF NOT EXISTS metrics_job_state (
    job_name TEXT PRIMARY KEY,
    last_processed_cdr_id BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Initial state for the processor
INSERT INTO metrics_job_state (job_name, last_processed_cdr_id) 
VALUES ('cdr_analytics_processor', 0)
ON CONFLICT (job_name) DO NOTHING;
