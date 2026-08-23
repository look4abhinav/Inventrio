-- ============================================================================
-- Inventrio · Dummy Pharmacy Data
-- Story: "Sharma Medical Store" — a small Indian pharmacy, early August 2026
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Manufacturers
-- ---------------------------------------------------------------------------

INSERT INTO manufacturers (name, contact_email, contact_phone, address) VALUES
('FDC Limited',    'sales@fdcindia.in',       '+91 22 4045 7000', 'Mumbai, Maharashtra'),
('Cipla Ltd',      'distributors@cipla.com',  '+91 22 2482 6000', 'Mumbai, Maharashtra'),
('Micro Labs Ltd', 'info@microlabs.in',       '+91 80 4110 5000', 'Bengaluru, Karnataka'),
('GSK Pharma',     'contact@gskpharma.in',    '+91 22 2495 9595', 'Mumbai, Maharashtra'),
('Alembic Pharma', 'reach@alembic.co.in',     '+91 265 228 0550', 'Vadodara, Gujarat'),
('Pfizer India',   'support@pfizerindia.in',  '+91 22 6616 6000', 'Mumbai, Maharashtra'),
('Abbott India',   'care@abbottindia.in',     '+91 22 2820 2600', 'Mumbai, Maharashtra');

-- ---------------------------------------------------------------------------
-- Categories & dosage forms
-- ---------------------------------------------------------------------------

INSERT INTO product_categories (name, description) VALUES
('Electrolytes & ORS',          'Oral rehydration solutions and electrolyte powders'),
('Analgesics & Antipyretics',   'Pain relief and fever medication'),
('Antibiotics',                 'Prescription anti-infective drugs'),
('Antacids & Digestives',       'Acidity and digestion relief'),
('Vitamins & Supplements',      'Nutritional supplements');

INSERT INTO dosage_forms (name) VALUES
('Sachet'), ('Tablet'), ('Syrup'), ('Capsule'), ('Drops');

-- ---------------------------------------------------------------------------
-- Products (brand-level SKUs)
-- ---------------------------------------------------------------------------

INSERT INTO products
(sku, brand_name, generic_name, manufacturer_id, category_id, dosage_form_id,
 strength, pack_size, unit, mrp, purchase_price, selling_price, gst_rate,
 requires_prescription, schedule_class, storage_instructions, reorder_level,
 api_source, api_code) VALUES
('P-001', 'Electral Powder', 'Oral Rehydration Salts (ORS)', 1, 1, 1,
 '21.8 g', 1, 'sachet', 22.50, 18.75, 22.50, 12,
 0, 'OTC', 'Store in a cool, dry place', 10, 'openfda', 'FD-ORS-218'),
('P-002', 'ORS-L',          'Oral Rehydration Salts (ORS)', 2, 1, 1,
 '21.8 g', 1, 'sachet', 23.00, 19.00, 23.00, 12,
 0, 'OTC', 'Store in a cool, dry place', 10, 'openfda', 'FD-ORS-218'),
('P-003', 'Dolo 650',       'Paracetamol',                 3, 2, 2,
 '650 mg', 15, 'strip', 33.00, 25.00, 30.00, 12,
 0, 'OTC', 'Store below 25 C', 30, 'openfda', 'FD-PCM-650'),
('P-004', 'Calpol 500',     'Paracetamol',                 4, 2, 2,
 '500 mg', 15, 'strip', 14.00, 10.00, 12.00, 12,
 0, 'OTC', 'Store below 25 C', 10, 'openfda', 'FD-PCM-500'),
('P-005', 'Azithral 500',   'Azithromycin',                5, 3, 2,
 '500 mg', 5, 'strip', 125.00, 90.00, 125.00, 12,
 1, 'Schedule H', 'Store in a cool, dry place', 5, 'openfda', 'FD-AZI-500'),
('P-006', 'Gelusil MPS',    'Aluminium Hydroxide + Simethicone', 6, 4, 3,
 '200 ml', 1, 'bottle', 120.00, 95.00, 120.00, 18,
 0, 'OTC', 'Shake well before use', 5, 'openfda', 'FD-GEL-200'),
('P-007', 'Limcee',         'Vitamin C (Ascorbic Acid)',   7, 5, 2,
 '500 mg', 15, 'strip', 25.00, 15.00, 25.00, 18,
 0, 'OTC', 'Store in a cool, dry place', 10, 'openfda', 'FD-VTC-500');

-- ---------------------------------------------------------------------------
-- Suppliers (pharma distributors)
-- ---------------------------------------------------------------------------

INSERT INTO suppliers (name, contact_person, phone, email, address, gstin) VALUES
('MedPlus Distributors', 'Suresh Patel',  '+91 98200 11223', 'orders@medplusdist.in',   'Andheri East, Mumbai',       '27AABCM1234F1Z5'),
('Sai Pharma Agencies',  'Anita Desai',   '+91 99870 44556', 'sales@saipharma.in',      'Viman Nagar, Pune',          '27AABCS5678G1Z2'),
('HealthBridge Wholesale','Ravi Menon',   '+91 98111 77889', 'desk@healthbridge.in',    'MG Road, Bengaluru',         '29AABCH9012H1Z8');

-- ---------------------------------------------------------------------------
-- Customers
-- ---------------------------------------------------------------------------

INSERT INTO customers (name, phone, email, address, age, allergies) VALUES
('Ramesh Kumar',  '+91 98765 00001', 'ramesh.k@example.com',  'Kothrud, Pune',     45, 'Penicillin'),
('Priya Sharma',  '+91 98765 00002', 'priya.sh@example.com',  'Bandra West, Mumbai', 62, 'None');

-- ---------------------------------------------------------------------------
-- Batches (all start at quantity 0 — the stock ledger fills them in below)
-- ---------------------------------------------------------------------------

INSERT INTO batches
(product_id, supplier_id, batch_number, mfg_date, expiry_date, quantity,
 purchase_price, mrp, discount_percent) VALUES
(1, 1, 'ELC-2026-01', '2026-01-10', '2028-01-09', 0, 18.75, 22.50, 0),   -- healthy stock
(1, 2, 'ELC-2025-08', '2025-07-15', '2026-08-31', 0, 18.75, 22.50, 0),   -- expiring soon
(1, 2, 'ELC-2024-06', '2024-06-01', '2026-06-30', 0, 18.75, 22.50, 0),   -- expired & written off
(1, 1, 'ELC-2026-09', '2026-07-20', '2027-12-31', 0, 18.75, 22.50, 5),   -- added by the AI agent
(2, 2, 'ORSL-2026-03', '2026-03-10', '2027-03-15', 0, 19.00, 23.00, 0),
(3, 1, 'DLO-2026-05',  '2026-05-01', '2027-05-01', 0, 25.00, 33.00, 0),  -- ends LOW on purpose
(4, 1, 'CAL-2026-02',  '2026-02-01', '2027-02-28', 0, 10.00, 14.00, 0),
(5, 2, 'AZI-2026-04',  '2026-04-01', '2027-04-20', 0, 90.00, 125.00, 0),
(6, 2, 'GEL-2026-01',  '2026-01-01', '2027-01-15', 0, 95.00, 120.00, 0),
(7, 3, 'LIM-2026-03',  '2026-03-01', '2027-03-10', 0, 15.00, 25.00, 0);

-- ---------------------------------------------------------------------------
-- Purchases + items
-- ---------------------------------------------------------------------------

INSERT INTO purchases (supplier_id, invoice_number, purchase_date, subtotal,
                       discount_amount, tax_amount, total_amount, status, notes, created_by)
VALUES
(2, 'INV-1000', '2025-08-01', 787.50, 0.00,  0.00,   787.50,  'completed', 'Opening stock', 'seed_script'),
(1, 'INV-1001', '2026-07-01', 2687.50, 0.00, 134.38, 2821.88, 'completed', 'Monthly refill', 'seed_script'),
(2, 'INV-1002', '2026-07-15', 3060.00, 153.00, 0.00,  2907.00, 'completed', '5% distributor discount', 'seed_script'),
(3, 'INV-1003', '2026-08-01', 600.00,  0.00,  0.00,   600.00,  'completed', 'Vitamin restock', 'seed_script'),
(1, 'INV-1004', '2026-08-15', 375.00,  18.75, 0.00,   356.25,  'completed', 'Added via AI agent', 'ai-agent:conv-1');

INSERT INTO purchase_items (purchase_id, product_id, batch_id, quantity,
                            unit_price, discount_percent, total_price, expiry_date)
VALUES
(1, 1, 2, 30, 18.75, 0, 562.50,  '2026-08-31'),
(1, 1, 3, 12, 18.75, 0, 225.00,  '2026-06-30'),
(2, 1, 1, 50, 18.75, 0, 937.50,  '2028-01-09'),
(2, 3, 6, 50, 25.00, 0, 1250.00, '2027-05-01'),
(2, 4, 7, 50, 10.00, 0, 500.00,  '2027-02-28'),
(3, 2, 5, 40, 19.00, 0, 760.00,  '2027-03-15'),
(3, 5, 8, 15, 90.00, 0, 1350.00, '2027-04-20'),
(3, 6, 9, 10, 95.00, 0, 950.00,  '2027-01-15'),
(4, 7, 10, 40, 15.00, 0, 600.00, '2027-03-10'),
(5, 1, 4, 20, 18.75, 5, 375.00,  '2027-12-31');

-- ---------------------------------------------------------------------------
-- Sales + items
-- ---------------------------------------------------------------------------

INSERT INTO sales (customer_id, sale_date, subtotal, discount_amount,
                   tax_amount, total_amount, payment_method, status, notes, created_by)
VALUES
(NULL, '2026-08-10 10:30:00', 450.00,  0.00,  0.00, 450.00,  'cash', 'completed', NULL, 'counter'),
(NULL, '2026-08-12 16:15:00', 387.50,  0.00,  0.00, 387.50,  'upi',  'completed', NULL, 'counter'),
(1,    '2026-08-13 11:00:00', 165.00,  0.00,  0.00, 165.00,  'card', 'completed', 'Ramesh - regular', 'ai-agent:conv-2'),
(2,    '2026-08-14 18:40:00', 2241.00, 41.00, 0.00, 2200.00, 'cash', 'completed', 'Bulk purchase, Rs 41 rounded off', 'counter');

INSERT INTO sale_items (sale_id, product_id, batch_id, quantity, unit_price,
                        discount_percent, total_price)
VALUES
(1, 1, 2, 20, 22.50, 0, 450.00),
(2, 1, 2, 7,  22.50, 0, 157.50),
(2, 2, 5, 10, 23.00, 0, 230.00),
(3, 3, 6, 5,  33.00, 0, 165.00),
(4, 3, 6, 35, 30.00, 0, 1050.00),
(4, 2, 5, 12, 23.00, 0, 276.00),
(4, 4, 7, 25, 12.00, 0, 300.00),
(4, 5, 8, 3,  125.00, 0, 375.00),
(4, 6, 9, 2,  120.00, 0, 240.00);

-- ---------------------------------------------------------------------------
-- Stock movements: replay purchases (+) then sales (-) into the ledger.
-- The trigger trg_movements_update_batch turns these into batch quantities.
-- ---------------------------------------------------------------------------

INSERT INTO stock_movements (batch_id, movement_type, quantity,
                             reference_type, reference_id, notes, recorded_by)
SELECT pi.batch_id, 'purchase', pi.quantity, 'purchase', pi.purchase_id,
       'Purchase ' || p.invoice_number, p.created_by
FROM purchase_items pi
JOIN purchases p ON p.puid = pi.purchase_id;

INSERT INTO stock_movements (batch_id, movement_type, quantity,
                             reference_type, reference_id, notes, recorded_by)
SELECT si.batch_id, 'sale', -si.quantity, 'sale', si.sale_id,
       'Sale #' || si.sale_id, s.created_by
FROM sale_items si
JOIN sales s ON s.said = si.sale_id;

-- Expired Electral batch written off (quantity 12 -> 0)
INSERT INTO stock_movements (batch_id, movement_type, quantity,
                             reference_type, reference_id, notes, recorded_by)
VALUES (3, 'expiry_write_off', -12, 'manual', NULL,
        'Expired 2026-06-30, discarded per FEFO policy', 'owner');

-- ---------------------------------------------------------------------------
-- AI agent layer: example conversations from the seed story
-- ---------------------------------------------------------------------------

INSERT INTO ai_conversations (user_message, agent_response, extracted_intent,
                              extracted_entities, status)
VALUES
('Add 20 packets of ORS - Electral',
 'Added 20 sachets of Electral Powder from MedPlus Distributors with 5% discount. New batch ELC-2026-09 expires 31-12-2027.',
 'add_stock',
 '{"product": "Electral Powder", "generic": "Oral Rehydration Salts", "quantity": 20, "unit": "sachets", "supplier": "MedPlus Distributors", "discount": "5%"}',
 'executed'),

('Sell 5 strips of Dolo 650 to Ramesh',
 'Sold 5 strips of Dolo 650 to Ramesh Kumar for Rs 165.00 (card payment). Stock updated.',
 'sell',
 '{"product": "Dolo 650", "quantity": 5, "unit": "strips", "customer": "Ramesh Kumar", "payment": "card"}',
 'executed'),

('Add 30 bottles of Calpol 500 from MedPlus with 10% discount',
 'Sure! I need two more details before adding the stock: the batch number and the expiry date of the Calpol 500 bottles.',
 'add_stock',
 '{"product": "Calpol 500", "quantity": 30, "unit": "bottles", "supplier": "MedPlus Distributors", "discount": "10%"}',
 'awaiting_clarification'),

('How much Dolo 650 stock is left?',
 'You have 10 strips of Dolo 650 left in batch DLO-2026-05 (expires 01-05-2027). This is below your reorder level of 30 strips - consider restocking.',
 'check_stock',
 '{"product": "Dolo 650", "query": "stock"}',
 'resolved');

INSERT INTO pending_clarifications (conversation_id, question, field_name,
                                    resolved, resolved_value, resolved_at)
VALUES
(1, 'What discount did the supplier offer on this purchase?', 'discount',
 1, '5%', '2026-08-15 09:12:00'),
(3, 'Could you share the batch number and expiry date of the Calpol 500 bottles?',
 'batch_number,expiry', 0, NULL, NULL);

INSERT INTO action_log (conversation_id, action_type, target_table, target_id,
                        details, status, error_message)
VALUES
(1, 'product_found',    'products',   1, '{"matched_by": "generic_name", "generic": "Oral Rehydration Salts"}', 'success', NULL),
(1, 'batch_added',      'batches',    4, '{"batch_number": "ELC-2026-09", "expiry": "2027-12-31", "discount": 5}', 'success', NULL),
(1, 'purchase_recorded','purchases',  5, '{"invoice": "INV-1004", "total": 356.25}', 'success', NULL),
(2, 'sale_recorded',    'sales',      3, '{"total": 165.00, "payment": "card"}', 'success', NULL),
(2, 'stock_updated',    'batches',    6, '{"quantity_after": 10}', 'success', NULL);

-- ---------------------------------------------------------------------------
-- Sanity checks (fail loudly if the seed story is inconsistent)
-- ---------------------------------------------------------------------------

SELECT CASE WHEN (SELECT quantity FROM batches WHERE batch_number = 'DLO-2026-05') = 10
       THEN 'OK: Dolo 650 is LOW as intended'
       ELSE 'FAIL: Dolo 650 quantity mismatch' END;

SELECT CASE WHEN (SELECT quantity FROM batches WHERE batch_number = 'ELC-2024-06') = 0
       THEN 'OK: expired batch written off'
       ELSE 'FAIL: expired batch not zeroed' END;

SELECT CASE WHEN (SELECT COUNT(*) FROM v_expiring_soon) >= 1
       THEN 'OK: expiring-soon view populated'
       ELSE 'FAIL: expiring-soon view empty' END;
