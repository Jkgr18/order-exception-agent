-- Orders table for the Order Exception Agent demo. ALL DATA IS FAKE.
CREATE TABLE orders (
    order_id          SERIAL PRIMARY KEY,
    order_number      TEXT        NOT NULL UNIQUE,
    customer_name     TEXT        NOT NULL,
    customer_email    TEXT        NOT NULL,
    product           TEXT        NOT NULL,
    order_value       NUMERIC(10,2) NOT NULL,

    -- shipping address
    ship_address1     TEXT        NOT NULL,
    ship_city         TEXT        NOT NULL,
    ship_state        CHAR(2)     NOT NULL,
    ship_zip          TEXT        NOT NULL,

    -- billing address (compared against shipping to spot anomalies)
    bill_city         TEXT        NOT NULL,
    bill_state        CHAR(2)     NOT NULL,
    bill_zip          TEXT        NOT NULL,

    order_date        DATE        NOT NULL,
    ship_date         DATE        NOT NULL,
    promised_date     DATE        NOT NULL,

    carrier           TEXT        NOT NULL,
    tracking_number   TEXT        NOT NULL,
    tracking_status   TEXT        NOT NULL CHECK (tracking_status IN
        ('label_created','in_transit','out_for_delivery','delivered','exception','returned')),
    last_scan_at      TIMESTAMPTZ,          -- NULL = carrier has never scanned the package
    last_scan_location TEXT,

    -- Free text typed by a customer. UNTRUSTED: a prompt-injection vector for agents.
    customer_note     TEXT
);

CREATE INDEX idx_orders_status ON orders (tracking_status);
CREATE INDEX idx_orders_promised ON orders (promised_date);
