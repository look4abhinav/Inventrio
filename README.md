# 💊 Inventrio

### Your Friendly AI Pharmacy Inventory Manager 🧠✨

> *"Add 20 packets of ORS – Electral."*
> *"How much Dolo 650 is left?"*
> *"Sell 5 strips of Azithral to Ramesh."*

That's it. No forms. No training. No technical person needed. **Inventrio** is an
AI-powered inventory manager that lets shopkeepers run their pharmacy by simply
**talking** to an agent in plain, natural language. 🗣️💬

---

## 🎯 The Vision

A shopkeeper walks in and says: *"Kal ka stock add kar do — 50 strips Dolo 650, MedPlus se."*
The agent should be able to:

1. 🧠 **Understand** the intent and extract entities (product, quantity, supplier, discount…)
2. 🔎 **Enrich** the product with details from a medical API (composition, category, schedule class…)
3. ❓ **Ask back** only for what's genuinely missing — *"What's the batch number and expiry date?"*
4. 💾 **Write safely** into the inventory database with full audit trails
5. 📊 **Answer questions** — stock levels, low-stock alerts, expiring batches, today's sales

No SQL, no UI forms, no training manuals. Just talk. 💬

---

## ✨ Current State

- ✅ **Database** — normalized SQLite schema with triggers, views & safety rails
- ✅ **Dummy data** — realistic "Sharma Medical Store" seed story
- ✅ **Query cheat sheet** — 40+ ready-to-run queries in `queries.sql`
- ✅ **Pydantic models** — all tables & views typed with constraints in `models/tables.py`
- ✅ **Chat classifier** — gatekeeper agent that filters off-topic messages (`agents/classifier.py`)
- ✅ **Inventory agent** — add stock, sell (FEFO), check stock & expiry, with a deterministic ask-back clarification loop (`agents/inventory.py`)
- 🚧 **Next up** — medical API enrichment (OpenFDA / NPPA)

📋 Full task status & roadmap live in **[TASKS.md](TASKS.md)** — the single source of truth.

---

## 🛠️ Tech Stack

- 🐍 **Python 3.13+** — the language
- 🤖 **Pydantic AI** — the agent framework (coming soon!)
- 🗃️ **SQLite 3** — zero-config, single-file database
- 📦 **uv** — project & dependency management

---

## 📁 Project Structure

```
Inventrio/
├── pyproject.toml
├── TASKS.md                 # 📋 Task board & roadmap (single source of truth)
├── tests/
│   └── test_agent_flow.py   # 🧪 Live end-to-end tests of the agent pipeline
└── src/
    └── inventrio/
        ├── __init__.py
        ├── main.py              # 🖥️ CLI entrypoint (chat REPL)
        ├── agents/              # 🤖 All AI agents in one place
        │   ├── __init__.py
        │   ├── llm.py           # 🔌 Shared chat-model config (minimax-m3)
        │   ├── classifier.py    # 🚪 Gatekeeper agent (+ its output model)
        │   └── inventory.py     # 💊 Inventory agent + tools + clarification loop
        ├── models/              # 🧩 Pydantic models
        │   ├── __init__.py
        │   └── tables.py        # One model per table/view in schema.sql
        └── database/            # 🗄️ SQL + typed repository
            ├── __init__.py
            ├── repository.py    # Typed SQLite layer (FEFO sales, ledger writes)
            ├── schema.sql       # 📐 All tables, constraints, triggers & views
            ├── seed.sql         # 🌱 Dummy pharmacy data ("Sharma Medical Store")
            ├── queries.sql      # 📝 40+ useful queries (stock, expiry, sales…)
            └── inventrio.db     # The built SQLite database (gitignored)
```

---

## 🗄️ Database Design

### The Big Picture 🖼️

```
        ┌──────────────┐   ┌──────────────────┐   ┌───────────┐
        │ manufacturers│   │ product_categories│   │ dosage_   │
        └──────┬───────┘   └────────┬─────────┘   │  forms    │
               │                    │             └─────┬─────┘
               ▼                    ▼                   ▼
        ┌───────────────────────────────────────────────┐
        │                  products 🧴                  │  ← master catalog,
        └─────┬──────────────────────────┬──────────────┘    enriched by API
              │                          │
              ▼                          ▼
      ┌──────────────┐           ┌──────────────┐
      │   suppliers 🚚│           │  customers 🧑 │
      └──────┬───────┘           └──────┬───────┘
             │                          │
             ▼                          ▼
      ┌──────────────┐           ┌──────────────┐
      │ purchases 📥 │           │   sales 📤   │
      │ purchase_    │           │   sale_      │
      │   items      │           │   items      │
      └──────┬───────┘           └──────┬───────┘
             │                          │
             └──────────┬───────────────┘
                        ▼
                 ┌──────────────┐
                 │  batches 🧪  │   ← batch no + expiry = pharmacy law
                 └──────┬───────┘
                        ▼
                 ┌──────────────┐
                 │ stock_move-  │   ← append-only ledger (audit trail)
                 │   ments 📒   │       triggers auto-update batch qty
                 └──────────────┘
```

### The AI Layer 🤖

```
ai_conversations 💬          pending_clarifications ❓       action_log 🧾
──────────────────          ──────────────────────────      ────────────────
user_message                conversation_id ─────────────►  conversation_id
agent_response              question                        action_type
extracted_intent ◄──add_stock/sell/check_stock/query        target_table + target_id
extracted_entities (JSON)   field_name (quantity/discount/…) status: success/failed
status: awaiting_clarification / executed / resolved        error_message
```

### Tables 📋

| Table | Purpose | Highlights |
|-------|---------|------------|
| `manufacturers` | Drug makers (Cipla, FDC…) | soft-delete via `is_active` |
| `product_categories` | Electrolytes, Antibiotics… | taxonomy for reports |
| `dosage_forms` | Sachet, Tablet, Syrup… | used by the agent to guess packs |
| `products` | Brand-level SKUs | MRP, prices, GST, Rx flag, **reorder level**, API links (`api_source`, `api_code`) |
| `suppliers` | Pharma distributors | GSTIN, contacts |
| `batches` | **Physical stock** | batch number + expiry are mandatory, per-batch discount |
| `purchases` / `purchase_items` | Stock-in orders | invoice number, item-level pricing |
| `customers` | Walk-ins & regulars | `allergies` field — it's a pharmacy! 😄 |
| `sales` / `sale_items` | Stock-out bills | payment method, discounts, tax |
| `stock_movements` | Append-only ledger | **trigger auto-updates batch quantities**; overselling raises a CHECK error 🛡️ |
| `ai_conversations` | What the user said & what the agent did | extracted intent + entities as JSON |
| `pending_clarifications` | Follow-up questions the agent asks | tracks `field_name` → `resolved_value` |
| `action_log` | Every DB write the agent makes | success / failed / rolled_back |

### Views 👓

| View | What it gives you |
|------|-------------------|
| `v_current_stock` | Every in-date batch with stock, **sorted FEFO** (first-expiry-first-out) |
| `v_stock_summary` | Per-product totals with `LOW`/`OK` stock status |
| `v_expiring_soon` | Batches expiring within 90 days — never sell expired meds! ⚠️ |
| `v_daily_sales` | Day-wise revenue, discounts & tax at a glance |

### Safety Rails 🛡️

- ✅ Foreign keys everywhere — no orphaned stock
- ✅ `CHECK` constraints: non-negative prices/quantities, expiry > mfg, discount 0–100%
- ✅ Unique `(product_id, batch_number)` — no duplicate batches
- ✅ Ledger-trigger guarantees batch qty always matches the movement history
- ✅ `updated_at` triggers keep timestamps honest

---

## 🌱 The Seed Story

The dummy data brings **"Sharma Medical Store"** to life (August 2026):

- 🏭 7 manufacturers, 7 products, 3 distributors, 2 regular customers
- 📥 5 purchase invoices, 📤 4 sales bills, 📒 a full movement ledger
- ⚠️ `Electral ELC-2025-08` is **expiring in 16 days**
- 🚨 `Dolo 650` is **LOW on stock** (10 strips vs reorder level 30)
- 🗑️ An expired Electral batch was correctly **written off**
- 🤖 4 AI conversations, including one that's still `awaiting_clarification`
  ("*What's the batch number and expiry date?*")

---

## 💬 Example Conversation

```
👤 User:  "Add 20 packets of ORS - Electral"
🤖 Agent: "Sure! To record 20 sachets of Electral Powder, I need the batch
           number, manufacturing date and expiry date."
           ← the question is persisted in pending_clarifications ❓

👤 User:  "Batch ELC-2026-10, mfg 2026-07-01, expiry 2027-06-30, 5% discount"
🤖 Agent: "Done! Added 20 sachets of Electral Powder, batch ELC-2026-10,
           expiry 2027-06-30, total Rs 356.25." ✅

👤 User:  "How much Dolo 650 stock is left?"
🤖 Agent: "10 strips left — below your reorder level of 30, so stock is LOW.
           You may want to restock soon." ⚠️

👤 User:  "Sell 5 strips of Dolo 650 to Ramesh, card payment"
🤖 Agent: "Done! Sold 5 strips to Ramesh at Rs 30/strip — total Rs 150.
           5 strips left." 💳
```

---

## 🚀 Getting Started

### 1. Clone & install

```bash
git clone <repo-url> inventrio && cd inventrio
uv sync
```

### 2. (Re)build the database

```bash
sqlite3 src/inventrio/database/inventrio.db < src/inventrio/database/schema.sql
sqlite3 src/inventrio/database/inventrio.db < src/inventrio/database/seed.sql
```

### 3. Talk to the agent 🤖

```bash
uv run python -m inventrio.main
```

Try things like *"Add 20 packets of ORS - Electral"*, *"How much Dolo 650 is left?"*,
or *"Sell 5 strips of Dolo 650 to Ramesh by card"* — it will ask back for batch
numbers and expiry dates when they're missing. 🗣️

### 4. Run the tests 🧪

```bash
uv run pytest tests/ -v
```

> Note: the tests are live integration tests — they call the real LLM
> (configured via `.env`), so they need network access.

### 5. Poke around the database 🔍

```bash
sqlite3 -header -column src/inventrio/database/inventrio.db \
  "SELECT * FROM v_stock_summary;"
```

| Try these fun queries | 
|---|
| `SELECT * FROM v_expiring_soon;` ⏳ |
| `SELECT * FROM ai_conversations WHERE status = 'awaiting_clarification';` ❓ |
| `SELECT * FROM stock_movements ORDER BY smid DESC LIMIT 10;` 📒 |
| `SELECT * FROM v_daily_sales;` 💰 |

💡 **Run them all:** `sqlite3 src/inventrio/database/inventrio.db < src/inventrio/database/queries.sql`

---

## 🗺️ Roadmap

See **[TASKS.md](TASKS.md)** for the full roadmap, feature backlog and changelog. 🎯

---

## 📜 License

Learning project — use it, break it, learn from it! 🎓

---

*Built with ❤️ + 🐍 to make inventory management as easy as a conversation.*
