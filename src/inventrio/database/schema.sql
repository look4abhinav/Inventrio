-- ============================================================================
-- Inventrio · Pharmacy Inventory Database Schema
-- SQLite 3 · designed for an AI-agent-driven inventory manager
-- ----------------------------------------------------------------------------
-- PK convention: short prefixed names (mid, pid, bid, said...)
-- FK convention: descriptive <entity>_id columns (product_id, supplier_id...)
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- 1. CATALOG: manufacturers, categories, dosage forms
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS manufacturers (
    mid           INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    contact_email TEXT,
    contact_phone TEXT,
    address       TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS product_categories (
    pcid        INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS dosage_forms (
    dfid INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- 2. PRODUCTS: brand-level SKUs, enriched later from a medical API
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS products (
    pid                   INTEGER PRIMARY KEY AUTOINCREMENT,
    sku                   TEXT    NOT NULL UNIQUE,
    brand_name            TEXT    NOT NULL,
    generic_name          TEXT    NOT NULL,
    manufacturer_id       INTEGER NOT NULL REFERENCES manufacturers (mid),
    category_id           INTEGER REFERENCES product_categories (pcid),
    dosage_form_id        INTEGER REFERENCES dosage_forms (dfid),
    strength              TEXT,             -- e.g. '500 mg', '21.8 g'
    pack_size             INTEGER NOT NULL DEFAULT 1 CHECK (pack_size > 0),
    unit                  TEXT    NOT NULL DEFAULT 'pack',  -- strip / bottle / sachet
    mrp                   REAL    NOT NULL CHECK (mrp >= 0),
    purchase_price        REAL    NOT NULL DEFAULT 0 CHECK (purchase_price >= 0),
    selling_price         REAL    NOT NULL DEFAULT 0 CHECK (selling_price >= 0),
    gst_rate              REAL    CHECK (gst_rate BETWEEN 0 AND 100),
    requires_prescription INTEGER NOT NULL DEFAULT 0 CHECK (requires_prescription IN (0, 1)),
    schedule_class        TEXT    CHECK (schedule_class IN ('OTC', 'Rx', 'Schedule H', 'Schedule H1', 'Schedule X')),
    storage_instructions  TEXT,             -- e.g. 'Store below 25 C'
    reorder_level         INTEGER NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
    is_active             INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    api_source            TEXT,             -- e.g. 'openfda', 'nppa'
    api_code              TEXT,             -- external id from the medical API
    created_at            TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- 3. SUPPLIERS: pharma distributors / wholesalers
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS suppliers (
    sid            INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL UNIQUE,
    contact_person TEXT,
    phone          TEXT,
    email          TEXT,
    address        TEXT,
    gstin          TEXT,
    is_active      INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- 4. BATCHES: the physical stock. Batch no + expiry are mandatory in pharmacy.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS batches (
    bid              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id       INTEGER NOT NULL REFERENCES products (pid),
    supplier_id      INTEGER REFERENCES suppliers (sid),
    batch_number     TEXT    NOT NULL,
    mfg_date         TEXT    NOT NULL,
    expiry_date      TEXT    NOT NULL,
    quantity         INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    purchase_price   REAL    NOT NULL CHECK (purchase_price >= 0),
    mrp              REAL    NOT NULL CHECK (mrp >= 0),
    discount_percent REAL    NOT NULL DEFAULT 0 CHECK (discount_percent BETWEEN 0 AND 100),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (expiry_date > mfg_date),
    UNIQUE (product_id, batch_number)
);

-- ---------------------------------------------------------------------------
-- 5. PURCHASES: stock-in orders from suppliers
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS purchases (
    puid            INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id     INTEGER REFERENCES suppliers (sid),
    invoice_number  TEXT,
    purchase_date   TEXT    NOT NULL DEFAULT (date('now')),
    subtotal        REAL    NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    discount_amount REAL    NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    tax_amount      REAL    NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    total_amount    REAL    NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    status          TEXT    NOT NULL DEFAULT 'completed'
                    CHECK (status IN ('pending', 'completed', 'cancelled')),
    notes           TEXT,
    created_by      TEXT,                    -- staff or AI agent session id
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS purchase_items (
    piid             INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id      INTEGER NOT NULL REFERENCES purchases (puid) ON DELETE CASCADE,
    product_id       INTEGER NOT NULL REFERENCES products (pid),
    batch_id         INTEGER REFERENCES batches (bid),
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    unit_price       REAL    NOT NULL CHECK (unit_price >= 0),
    discount_percent REAL    NOT NULL DEFAULT 0 CHECK (discount_percent BETWEEN 0 AND 100),
    total_price      REAL    NOT NULL CHECK (total_price >= 0),
    expiry_date      TEXT
);

-- ---------------------------------------------------------------------------
-- 6. CUSTOMERS: walk-ins & regulars (allergies matter in a pharmacy!)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS customers (
    cid        INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    phone      TEXT UNIQUE,
    email      TEXT,
    address    TEXT,
    age        INTEGER CHECK (age > 0),
    allergies  TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- 7. SALES: stock-out transactions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sales (
    said            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     INTEGER REFERENCES customers (cid),
    sale_date       TEXT    NOT NULL DEFAULT (datetime('now')),
    subtotal        REAL    NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    discount_amount REAL    NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    tax_amount      REAL    NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    total_amount    REAL    NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    payment_method  TEXT    CHECK (payment_method IN ('cash', 'upi', 'card', 'credit', 'other')),
    status          TEXT    NOT NULL DEFAULT 'completed'
                    CHECK (status IN ('completed', 'refunded', 'cancelled')),
    notes           TEXT,
    created_by      TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sale_items (
    siid             INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id          INTEGER NOT NULL REFERENCES sales (said) ON DELETE CASCADE,
    product_id       INTEGER NOT NULL REFERENCES products (pid),
    batch_id         INTEGER REFERENCES batches (bid),   -- FEFO: which batch it left from
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    unit_price       REAL    NOT NULL CHECK (unit_price >= 0),
    discount_percent REAL    NOT NULL DEFAULT 0 CHECK (discount_percent BETWEEN 0 AND 100),
    total_price      REAL    NOT NULL CHECK (total_price >= 0)
);

-- ---------------------------------------------------------------------------
-- 8. STOCK MOVEMENTS: append-only ledger of every in/out (audit trail)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS stock_movements (
    smid           INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id       INTEGER NOT NULL REFERENCES batches (bid),
    movement_type  TEXT    NOT NULL CHECK (movement_type IN
                   ('purchase', 'sale', 'adjustment', 'return_in',
                    'return_out', 'expiry_write_off')),
    quantity       INTEGER NOT NULL CHECK (quantity != 0),  -- + in / - out
    reference_type TEXT    CHECK (reference_type IN ('purchase', 'sale', 'adjustment', 'manual')),
    reference_id   INTEGER,
    notes          TEXT,
    recorded_by    TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- 9. AI AGENT LAYER: conversations, follow-up questions, executed actions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ai_conversations (
    convid             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_message       TEXT NOT NULL,
    agent_response     TEXT,
    extracted_intent   TEXT,                  -- add_stock / sell / check_stock / query
    extracted_entities TEXT,                  -- JSON: {product, quantity, brand, ...}
    status             TEXT NOT NULL DEFAULT 'resolved'
                       CHECK (status IN ('processing', 'resolved', 'awaiting_clarification', 'executed', 'failed')),
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pending_clarifications (
    clid            INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES ai_conversations (convid) ON DELETE CASCADE,
    question        TEXT NOT NULL,            -- what the agent asked the user
    field_name      TEXT NOT NULL,            -- quantity / discount / batch_number / expiry ...
    resolved        INTEGER NOT NULL DEFAULT 0 CHECK (resolved IN (0, 1)),
    resolved_value  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT
);

CREATE TABLE IF NOT EXISTS action_log (
    alid            INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES ai_conversations (convid) ON DELETE SET NULL,
    action_type     TEXT NOT NULL,            -- product_created / batch_added / sale_recorded ...
    target_table    TEXT,
    target_id       INTEGER,
    details         TEXT,                     -- JSON snapshot of the change
    status          TEXT NOT NULL DEFAULT 'success'
                    CHECK (status IN ('success', 'failed', 'rolled_back')),
    error_message   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- INDEXES
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_products_generic         ON products (generic_name);
CREATE INDEX IF NOT EXISTS idx_products_brand           ON products (brand_name);
CREATE INDEX IF NOT EXISTS idx_batches_product          ON batches (product_id);
CREATE INDEX IF NOT EXISTS idx_batches_expiry           ON batches (expiry_date);
CREATE INDEX IF NOT EXISTS idx_batches_expired          ON batches (expiry_date) WHERE quantity > 0;
CREATE INDEX IF NOT EXISTS idx_movements_batch          ON stock_movements (batch_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_batch         ON sale_items (batch_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase  ON purchase_items (purchase_id);
CREATE INDEX IF NOT EXISTS idx_clarifications_conversation ON pending_clarifications (conversation_id);

-- ---------------------------------------------------------------------------
-- TRIGGERS: keep updated_at fresh
-- ---------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS trg_products_updated AFTER UPDATE ON products
BEGIN
    UPDATE products SET updated_at = datetime('now') WHERE pid = NEW.pid;
END;

CREATE TRIGGER IF NOT EXISTS trg_batches_updated AFTER UPDATE ON batches
BEGIN
    UPDATE batches SET updated_at = datetime('now') WHERE bid = NEW.bid;
END;

CREATE TRIGGER IF NOT EXISTS trg_suppliers_updated AFTER UPDATE ON suppliers
BEGIN
    UPDATE suppliers SET updated_at = datetime('now') WHERE sid = NEW.sid;
END;

CREATE TRIGGER IF NOT EXISTS trg_customers_updated AFTER UPDATE ON customers
BEGIN
    UPDATE customers SET updated_at = datetime('now') WHERE cid = NEW.cid;
END;

CREATE TRIGGER IF NOT EXISTS trg_manufacturers_updated AFTER UPDATE ON manufacturers
BEGIN
    UPDATE manufacturers SET updated_at = datetime('now') WHERE mid = NEW.mid;
END;

-- Stock movements are the single source of truth:
-- every ledger row automatically adjusts the batch's on-hand quantity.
-- (Overselling raises a CHECK violation, protecting stock integrity.)
CREATE TRIGGER IF NOT EXISTS trg_movements_update_batch AFTER INSERT ON stock_movements
BEGIN
    UPDATE batches SET quantity = quantity + NEW.quantity WHERE bid = NEW.batch_id;
END;

-- ---------------------------------------------------------------------------
-- VIEWS
-- ---------------------------------------------------------------------------

-- Every in-date batch that still has stock, sorted for FEFO picking.
CREATE VIEW IF NOT EXISTS v_current_stock AS
SELECT
    b.bid                                       AS batch_id,
    b.product_id,
    p.brand_name,
    p.generic_name,
    p.strength,
    df.name                                     AS dosage_form,
    b.batch_number,
    b.mfg_date,
    b.expiry_date,
    b.quantity,
    b.mrp,
    b.discount_percent,
    p.requires_prescription,
    ROUND(julianday(b.expiry_date) - julianday(date('now'))) AS days_to_expiry
FROM batches b
JOIN products p   ON p.pid = b.product_id
LEFT JOIN dosage_forms df ON df.dfid = p.dosage_form_id
WHERE b.quantity > 0
  AND p.is_active = 1
ORDER BY b.expiry_date ASC;

-- Per-product totals + low-stock / expiry flags (what the agent answers with).
CREATE VIEW IF NOT EXISTS v_stock_summary AS
SELECT
    p.pid                                             AS product_id,
    p.brand_name,
    p.generic_name,
    p.strength,
    COALESCE(SUM(b.quantity), 0)                      AS total_stock,
    p.reorder_level,
    CASE WHEN COALESCE(SUM(b.quantity), 0) <= p.reorder_level
         THEN 'LOW' ELSE 'OK' END                     AS stock_status,
    MIN(b.expiry_date)                                AS earliest_expiry,
    MIN(ROUND(julianday(b.expiry_date) - julianday(date('now'))))
                                                      AS min_days_to_expiry,
    COUNT(DISTINCT b.bid)                             AS active_batches
FROM products p
LEFT JOIN batches b ON b.product_id = p.pid AND b.quantity > 0
WHERE p.is_active = 1
GROUP BY p.pid;

-- Batches expiring within the next 90 days (or already expired).
CREATE VIEW IF NOT EXISTS v_expiring_soon AS
SELECT
    b.bid,
    p.brand_name,
    p.generic_name,
    b.batch_number,
    b.quantity,
    b.expiry_date,
    ROUND(julianday(b.expiry_date) - julianday(date('now'))) AS days_to_expiry
FROM batches b
JOIN products p ON p.pid = b.product_id
WHERE b.quantity > 0
  AND julianday(b.expiry_date) - julianday(date('now')) <= 90
ORDER BY b.expiry_date ASC;

-- Today's business at a glance.
CREATE VIEW IF NOT EXISTS v_daily_sales AS
SELECT
    date(sale_date)          AS day,
    COUNT(*)                 AS invoices,
    SUM(subtotal)            AS subtotal,
    SUM(discount_amount)     AS discounts,
    SUM(tax_amount)          AS tax,
    SUM(total_amount)        AS revenue
FROM sales
WHERE status = 'completed'
GROUP BY date(sale_date)
ORDER BY day DESC;
