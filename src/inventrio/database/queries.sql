-- ============================================================================
-- Inventrio · queries.sql — the "cheat sheet" of every useful query
-- ----------------------------------------------------------------------------
-- Run the whole file:        sqlite3 src/inventrio/database/inventrio.db < queries.sql
-- (or open a shell:          sqlite3 src/inventrio/database/inventrio.db)
-- ----------------------------------------------------------------------------
-- Each section maps to a real-world pharmacy task and/or an AI-agent intent.
-- Replace example values (LIKE patterns, dates) as needed.
-- ============================================================================

.mode column
.headers on
.width 30 20 10 10 12 12 6

-- ============================================================================
-- 1. PRODUCT LOOKUPS  🔍  (agent intent: match spoken name → product)
-- ============================================================================

-- 1.1 Fuzzy search by brand or generic name — the agent's first move
SELECT pid, sku, brand_name, generic_name, strength
FROM products
WHERE brand_name   LIKE '%dolo%'
   OR generic_name LIKE '%dolo%';

-- 1.2 Full catalog with manufacturer & category
SELECT p.pid, p.brand_name, p.generic_name, p.strength,
       m.name AS manufacturer, c.name AS category,
       p.mrp, p.selling_price, p.reorder_level,
       CASE p.requires_prescription WHEN 1 THEN 'Rx' ELSE 'OTC' END AS rx
FROM products p
JOIN manufacturers m        ON m.mid = p.manufacturer_id
LEFT JOIN product_categories c ON c.pcid = p.category_id
WHERE p.is_active = 1
ORDER BY p.brand_name;

-- 1.3 Products still missing API enrichment (the agent should fill these)
SELECT pid, brand_name, generic_name, api_source, api_code
FROM products
WHERE api_code IS NULL OR api_source IS NULL;

-- 1.4 Products supplied by a specific manufacturer
SELECT p.brand_name, p.generic_name, p.mrp
FROM products p
JOIN manufacturers m ON m.mid = p.manufacturer_id
WHERE m.name = 'Cipla Ltd';

-- 1.5 Rx-only products (agent must warn before selling without prescription)
SELECT brand_name, generic_name, schedule_class
FROM products
WHERE requires_prescription = 1;

-- ============================================================================
-- 2. STOCK  📊  (agent intent: check_stock)
-- ============================================================================

-- 2.1 Everything at a glance: totals + LOW/OK flag
SELECT * FROM v_stock_summary;

-- 2.2 Stock of one product, broken down by batch (FEFO order)
SELECT p.brand_name, b.batch_number, b.quantity, b.expiry_date,
       ROUND(julianday(b.expiry_date) - julianday(date('now'))) AS days_left
FROM batches b
JOIN products p ON p.pid = b.product_id
WHERE p.brand_name LIKE '%Dolo%' AND b.quantity > 0
ORDER BY b.expiry_date;

-- 2.3 LOW-stock alerts (below or at reorder level)
SELECT * FROM v_stock_summary
WHERE stock_status = 'LOW'
ORDER BY total_stock ASC;

-- 2.4 Completely out of stock
SELECT p.brand_name, p.generic_name, p.reorder_level
FROM products p
WHERE p.is_active = 1
  AND NOT EXISTS (SELECT 1 FROM batches b
                  WHERE b.product_id = p.pid AND b.quantity > 0);

-- 2.5 Inventory valuation at purchase price (cost of stock on hand)
SELECT p.brand_name,
       SUM(b.quantity)                                   AS units,
       ROUND(SUM(b.quantity * b.purchase_price), 2)      AS cost_value,
       ROUND(SUM(b.quantity * b.mrp), 2)                 AS mrp_value
FROM batches b
JOIN products p ON p.pid = b.product_id
WHERE b.quantity > 0
GROUP BY p.pid
ORDER BY cost_value DESC;

-- 2.6 Discounts given on the stock currently on hand
SELECT p.brand_name, b.batch_number, b.discount_percent, b.quantity
FROM batches b
JOIN products p ON p.pid = b.product_id
WHERE b.quantity > 0 AND b.discount_percent > 0;

-- ============================================================================
-- 3. EXPIRY & FEFO  ⏳  (never sell expired medicine!)
-- ============================================================================

-- 3.1 Expiring within 90 days (or already expired)
SELECT * FROM v_expiring_soon;

-- 3.2 Already-expired stock that must be pulled from shelves NOW
SELECT p.brand_name, b.batch_number, b.quantity, b.expiry_date,
       ROUND(julianday(date('now')) - julianday(b.expiry_date)) AS days_expired
FROM batches b
JOIN products p ON p.pid = b.product_id
WHERE b.quantity > 0 AND b.expiry_date < date('now')
ORDER BY b.expiry_date;

-- 3.3 FEFO pick order for a sale: which batch to serve first
SELECT b.bid, b.batch_number, b.quantity, b.expiry_date
FROM batches b
JOIN products p ON p.pid = b.product_id
WHERE p.brand_name LIKE '%Electral%' AND b.quantity > 0
ORDER BY b.expiry_date ASC;

-- 3.4 Batches expiring in a specific month (planning promos)
SELECT p.brand_name, b.batch_number, b.quantity, b.expiry_date
FROM batches b
JOIN products p ON p.pid = b.product_id
WHERE b.quantity > 0
  AND b.expiry_date BETWEEN '2026-12-01' AND '2026-12-31';

-- ============================================================================
-- 4. PURCHASES  📥  (agent intent: add_stock)
-- ============================================================================

-- 4.1 Recent purchase orders
SELECT puid, invoice_number, purchase_date, total_amount, status
FROM purchases
ORDER BY purchase_date DESC
LIMIT 10;

-- 4.2 Full detail of one purchase (items + batch + product)
SELECT pi.purchase_id, p.brand_name, pi.quantity, pi.unit_price,
       pi.discount_percent, pi.total_price, b.batch_number, pi.expiry_date
FROM purchase_items pi
JOIN products p ON p.pid = pi.product_id
LEFT JOIN batches b ON b.bid = pi.batch_id
WHERE pi.purchase_id = 5;

-- 4.3 How much we bought from each supplier (all time)
SELECT s.name AS supplier,
       COUNT(DISTINCT pu.puid)      AS orders,
       ROUND(SUM(pu.total_amount), 2) AS total_value
FROM purchases pu
JOIN suppliers s ON s.sid = pu.supplier_id
WHERE pu.status = 'completed'
GROUP BY s.sid
ORDER BY total_value DESC;

-- 4.4 Purchases in a date range (e.g. this month)
SELECT puid, invoice_number, purchase_date, total_amount
FROM purchases
WHERE purchase_date >= date('now', 'start of month')
  AND status = 'completed';

-- 4.5 Pending (not yet completed) purchase orders
SELECT puid, supplier_id, invoice_number, purchase_date, total_amount
FROM purchases
WHERE status = 'pending';

-- 4.6 Cheapest recent price we paid per product (negotiation aid)
SELECT p.brand_name,
       MIN(pi.unit_price) AS lowest,
       MAX(pi.unit_price) AS highest,
       ROUND(AVG(pi.unit_price), 2) AS average
FROM purchase_items pi
JOIN products p ON p.pid = pi.product_id
GROUP BY p.pid;

-- ============================================================================
-- 5. SALES  📤  (agent intent: sell / billing)
-- ============================================================================

-- 5.1 Today's business
SELECT * FROM v_daily_sales WHERE day = date('now');

-- 5.2 Sales in a date range
SELECT said, sale_date, payment_method, total_amount, status
FROM sales
WHERE sale_date BETWEEN '2026-08-01' AND '2026-08-31'
ORDER BY sale_date;

-- 5.3 Top-selling products (by units and revenue)
SELECT p.brand_name,
       SUM(si.quantity)             AS units_sold,
       ROUND(SUM(si.total_price), 2) AS revenue
FROM sale_items si
JOIN products p ON p.pid = si.product_id
JOIN sales s    ON s.said = si.sale_id AND s.status = 'completed'
GROUP BY p.pid
ORDER BY units_sold DESC;

-- 5.4 Revenue by payment method
SELECT COALESCE(payment_method, 'unknown') AS method,
       COUNT(*) AS bills,
       ROUND(SUM(total_amount), 2) AS collected
FROM sales
WHERE status = 'completed'
GROUP BY payment_method;

-- 5.5 A full bill (for receipt printing)
SELECT si.sale_id, p.brand_name, si.quantity, si.unit_price,
       si.discount_percent, si.total_price, b.batch_number
FROM sale_items si
JOIN products p ON p.pid = si.product_id
LEFT JOIN batches b ON b.bid = si.batch_id
WHERE si.sale_id = 4;

-- 5.6 Discounts given to customers (Rs 41 on sale #4, etc.)
SELECT said, sale_date, subtotal, discount_amount, total_amount
FROM sales
WHERE discount_amount > 0;

-- 5.7 Monthly revenue trend (last 6 months)
SELECT strftime('%Y-%m', sale_date) AS month,
       COUNT(*)                     AS bills,
       ROUND(SUM(total_amount), 2)  AS revenue
FROM sales
WHERE status = 'completed'
  AND sale_date >= date('now', '-6 months')
GROUP BY month
ORDER BY month;

-- ============================================================================
-- 6. CUSTOMERS  🧑
-- ============================================================================

-- 6.1 Customer list (allergies matter in a pharmacy!)
SELECT cid, name, phone, age, allergies FROM customers;

-- 6.2 Purchase history of one customer
SELECT s.said, s.sale_date, s.total_amount, s.payment_method
FROM sales s
JOIN customers c ON c.cid = s.customer_id
WHERE c.name LIKE '%Ramesh%'
ORDER BY s.sale_date DESC;

-- 6.3 Products bought by one customer (for repeat-order suggestions)
SELECT p.brand_name, SUM(si.quantity) AS total_bought
FROM sale_items si
JOIN sales s    ON s.said = si.sale_id
JOIN customers c ON c.cid = s.customer_id
JOIN products p ON p.pid = si.product_id
WHERE c.name LIKE '%Ramesh%'
GROUP BY p.pid
ORDER BY total_bought DESC;

-- 6.4 Who spends the most? (top customers)
SELECT c.name, COUNT(s.said) AS visits, ROUND(SUM(s.total_amount), 2) AS lifetime
FROM sales s
JOIN customers c ON c.cid = s.customer_id
WHERE s.status = 'completed'
GROUP BY c.cid
ORDER BY lifetime DESC;

-- ============================================================================
-- 7. STOCK MOVEMENTS (AUDIT TRAIL)  📒
-- ============================================================================

-- 7.1 Latest 20 movements across the shop
SELECT sm.smid, p.brand_name, b.batch_number, sm.movement_type,
       sm.quantity, sm.reference_type, sm.reference_id, sm.created_at
FROM stock_movements sm
JOIN batches b   ON b.bid = sm.batch_id
JOIN products p  ON p.pid = b.product_id
ORDER BY sm.smid DESC
LIMIT 20;

-- 7.2 Complete history of a single batch
SELECT smid, movement_type, quantity, reference_type, reference_id, notes, created_at
FROM stock_movements
WHERE batch_id = 4
ORDER BY smid;

-- 7.3 Write-offs and adjustments only (damage/expiry events)
SELECT sm.smid, p.brand_name, b.batch_number, sm.quantity, sm.notes, sm.created_at
FROM stock_movements sm
JOIN batches b  ON b.bid = sm.batch_id
JOIN products p ON p.pid = b.product_id
WHERE sm.movement_type IN ('expiry_write_off', 'adjustment');

-- 7.4 Net stock movement per product this month
SELECT p.brand_name,
       SUM(sm.quantity) AS net_change
FROM stock_movements sm
JOIN batches b  ON b.bid = sm.batch_id
JOIN products p ON p.pid = b.product_id
WHERE sm.created_at >= date('now', 'start of month')
GROUP BY p.pid
ORDER BY net_change DESC;

-- 7.5 Ledger integrity check: movement math vs. batch quantity
--     (0 rows = everything reconciles)
SELECT b.bid, b.batch_number, b.quantity AS stored_qty,
       COALESCE((SELECT SUM(quantity) FROM stock_movements
                 WHERE batch_id = b.bid), 0) AS ledger_qty
FROM batches b
WHERE b.quantity != COALESCE((SELECT SUM(quantity) FROM stock_movements
                              WHERE batch_id = b.bid), 0);

-- ============================================================================
-- 8. AI AGENT LAYER  🤖  (conversations, clarifications, actions)
-- ============================================================================

-- 8.1 Conversations awaiting a user answer right now
SELECT c.convid, c.user_message, pc.question, pc.field_name, pc.created_at
FROM pending_clarifications pc
JOIN ai_conversations c ON c.convid = pc.conversation_id
WHERE pc.resolved = 0
ORDER BY pc.created_at;

-- 8.2 Recent conversations with status
SELECT convid, user_message, extracted_intent, status, created_at
FROM ai_conversations
ORDER BY convid DESC
LIMIT 10;

-- 8.3 Everything the agent has ever written to the DB (audit of AI actions)
SELECT alid, conversation_id, action_type, target_table, target_id,
       details, status, error_message, created_at
FROM action_log
ORDER BY alid DESC;

-- 8.4 Failed agent actions (debugging!)
SELECT * FROM action_log WHERE status != 'success';

-- 8.5 What intents do users ask for most? (agent usage analytics)
SELECT extracted_intent, COUNT(*) AS times
FROM ai_conversations
GROUP BY extracted_intent
ORDER BY times DESC;

-- 8.6 Clarifications that took the longest to resolve
SELECT c.user_message, pc.question, pc.created_at, pc.resolved_at,
       ROUND(julianday(pc.resolved_at) - julianday(pc.created_at), 1) AS days_open
FROM pending_clarifications pc
JOIN ai_conversations c ON c.convid = pc.conversation_id
WHERE pc.resolved = 1;

-- ============================================================================
-- 9. PROFIT & REPORTS  💰
-- ============================================================================

-- 9.1 Margin per product (selling price vs purchase price)
SELECT p.brand_name,
       p.purchase_price,
       p.selling_price,
       ROUND(p.selling_price - p.purchase_price, 2)     AS margin_per_unit,
       ROUND((p.selling_price - p.purchase_price) * 100.0
             / NULLIF(p.selling_price, 0), 1)           AS margin_pct
FROM products p
ORDER BY margin_pct DESC;

-- 9.2 Realised profit this month (revenue − cost of goods sold)
SELECT ROUND(SUM(si.total_price) - SUM(si.quantity * b.purchase_price), 2) AS gross_profit
FROM sale_items si
JOIN sales s   ON s.said = si.sale_id AND s.status = 'completed'
JOIN batches b ON b.bid = si.batch_id
WHERE s.sale_date >= date('now', 'start of month');

-- 9.3 Which product made the most profit this month?
SELECT p.brand_name,
       ROUND(SUM(si.total_price) - SUM(si.quantity * b.purchase_price), 2) AS profit
FROM sale_items si
JOIN sales s   ON s.said = si.sale_id AND s.status = 'completed'
JOIN batches b ON b.bid = si.batch_id
JOIN products p ON p.pid = si.product_id
WHERE s.sale_date >= date('now', 'start of month')
GROUP BY p.pid
ORDER BY profit DESC;

-- 9.4 Stock about to expire = money at risk
SELECT ROUND(SUM(b.quantity * b.purchase_price), 2) AS at_risk_value
FROM v_expiring_soon v
JOIN batches b ON b.bid = v.bid
WHERE v.days_to_expiry BETWEEN 0 AND 90;

-- 9.5 Complete daily snapshot (sales + purchases side by side)
SELECT date(s.sale_date) AS day,
       ROUND(SUM(s.total_amount), 2) AS sold,
       (SELECT ROUND(SUM(pu.total_amount), 2) FROM purchases pu
        WHERE date(pu.purchase_date) = date(s.sale_date)
          AND pu.status = 'completed') AS bought
FROM sales s
WHERE s.status = 'completed'
GROUP BY day
ORDER BY day DESC;
