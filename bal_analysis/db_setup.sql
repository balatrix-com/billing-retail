-- CDR Table (Target)
CREATE TABLE cdr (
    cdr_id BIGSERIAL PRIMARY KEY,
    call_uuid UUID NOT NULL,
    customer_id TEXT NOT NULL,
    caller TEXT NOT NULL,
    callee TEXT NOT NULL,
    last_destination TEXT,
    direction TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    answer_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ NOT NULL,
    duration_sec INTEGER NOT NULL,
    billsec INTEGER NOT NULL,
    dest_type VARCHAR(50),
    dest_value VARCHAR(100),
    status_code VARCHAR(50),
    call_status VARCHAR(50),
    ingress_trunk TEXT,
    egress_trunk TEXT,
    route_id TEXT,
    gateway_id TEXT,
    currency CHAR(3) NOT NULL,
    ratecard_id BIGINT,
    billed_amount NUMERIC(12,6) NOT NULL DEFAULT 0,
    transaction_id BIGINT,
    is_rated BOOLEAN NOT NULL DEFAULT false,
    rated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Analytics State Table
CREATE TABLE IF NOT EXISTS analytics_state (
    processor_name TEXT PRIMARY KEY,
    last_cdr_id BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Initial state for the processor
INSERT INTO analytics_state (processor_name, last_cdr_id) 
VALUES ('cdr_analytics_processor', 0)
ON CONFLICT (processor_name) DO NOTHING;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_cdr_id ON cdr(cdr_id);
CREATE INDEX IF NOT EXISTS idx_cdr_start_time ON cdr(start_time);
CREATE INDEX IF NOT EXISTS idx_cdr_customer_id ON cdr(customer_id);
