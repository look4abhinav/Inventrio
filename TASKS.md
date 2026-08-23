# 📋 Inventrio — Task Board

> The single source of truth for what's done, what's next, and what we dream about.
> **README.md** stays in sync with this file — update both when a task moves. 🔄

---

## 🏷️ Status Legend

| Emoji | Meaning |
|-------|---------|
| ✅ | Done |
| 🚧 | In progress / next up |
| 💭 | Planned / dream |
| ❌ | Dropped |

---

## ✨ Feature Backlog

| # | Area | Details | Status | Notes |
|---|------|---------|--------|-------|
| 1 | 🗄️ Database | Normalized SQLite schema: products, batches, purchases, sales, stock ledger, AI conversation layer | ✅ | `src/inventrio/database/schema.sql` |
| 2 | 🌱 Dummy Data | Realistic "Sharma Medical Store" seed story with expiring & low-stock demos | ✅ | `src/inventrio/database/seed.sql` |
| 3 | 📝 Query Cheat Sheet | All useful queries for stock, expiry, purchases, sales, audit & the AI layer | ✅ | `src/inventrio/database/queries.sql` |
| 4 | 🧩 Pydantic Models | Typed models for all 15 tables + 4 views with DB-mirrored constraints & relationships | ✅ | `src/inventrio/models/tables.py` |
| 5 | 🚪 Chat Classifier | Gatekeeper agent that rejects off-topic/mixed messages before they reach the inventory agent | ✅ | `src/inventrio/agents/classifier.py` |
| 6 | 🤖 Pydantic AI Agent | Inventory agent: add-stock / sell / check-stock / expiring tools, DB layer, deterministic clarification loop | ✅ | `src/inventrio/agents/inventory.py`, `database/repository.py`, `agents/llm.py` |
| 7 | 🔎 Medical API | Enrich products via external drug APIs (OpenFDA, NPPA…) | 🚧 | Next up! Needs API key research |
| 8 | ❓ Clarifications | Agent asks follow-ups for missing batch/expiry/discount/quantity | ✅ | Structured-output loop, backed by `pending_clarifications` |
| 9 | 🧾 Billing & GST | Auto-computed invoices with tax breakdown | 💭 | Tables already support it |
| 10 | 🔊 Voice Input | Speech-to-text for true "just talk" experience | 💭 | |
| 11 | 📈 Dashboards | Daily/monthly reports from the views | 💭 | `v_daily_sales` ready |

---

## 🗺️ Roadmap Checklist

- [x] 📐 SQLite schema with triggers, views & safety rails *(feature #1)*
- [x] 🌱 Realistic dummy pharmacy dataset *(feature #2)*
- [x] 📝 Query cheat sheet with 40+ ready-to-run queries *(feature #3)*
- [x] 🧩 Pydantic models for all tables & views *(feature #4)*
- [x] 🚪 Chat classifier gatekeeper with strict mixed-message rejection *(feature #5)*
- [x] 🤖 Inventory agent with DB tools + deterministic clarification loop *(feature #6)*
- [ ] 🔎 Medical API enrichment (OpenFDA / NPPA) for new products *(feature #7)*
- [x] ❓ Clarification loop backed by `pending_clarifications` *(feature #8)*
- [ ] 🧾 Receipt generation from `sales` + `sale_items` *(feature #9)*
- [ ] 🔊 Voice input so shopkeepers literally just talk *(feature #10)*
- [ ] 📈 Daily/monthly dashboards from the views *(feature #11)*

---

## 🔄 How We Work

1. Pick the next 🚧 task from the backlog.
2. Implement it. ✅
3. Move it to ✅ here **and** update the "Current State" section in `README.md`.
4. Add a line to the [Changelog](#changelog) below.

---

## 📜 Changelog

| Date | Change |
|------|--------|
| 2026-08-15 | 🗄️ Schema + 🌱 seed data done; database built & verified. Task board created. |
| 2026-08-15 | 📝 `queries.sql` added — 40+ queries across product lookup, stock, expiry/FEFO, purchases, sales, customers, audit, AI layer & profit reports. Database rebuilt. |
| 2026-08-15 | 🧩 Pydantic models created for all 15 tables + 4 views (now `models/tables.py`). Mirrors DB constraints (CHECKs, defaults, Literals) and adds read-side relationships. All 94 seed rows validate; bad data (expiry<=mfg, qty=0 movement, discount>100) is rejected. |
| 2026-08-15 | 🔄 Renamed all PK columns from `id` to short prefixed names (`mid`, `pid`, `bid`, `said`…) across schema, seed, queries, models & docs. FKs keep descriptive `<entity>_id` names. DB rebuilt. |
| 2026-08-16 | 🚪 Chat classifier agent polished: detailed gatekeeper instructions (mixed-message rejection, greeting rules, language-agnostic), output renamed to `ClassificationResult` with `is_related: bool` + one-sentence `reason`. Verified live: mixed → False, clean pharmacy → True, off-topic → False. |
| 2026-08-16 | 🤖 Inventory agent built: `db.py` (typed SQLite layer, FEFO sales, ledger via triggers), `llm.py` (shared chat model), `inventory_agent.py` with 7 tools + structured `InventoryReply` output. Clarification loop is deterministic via the `clarification` output field persisted to `pending_clarifications`; dynamic instructions re-surface open questions. 6-scenario E2E test passes: ask-back → answer → purchase recorded; sale with FEFO; oversell refused; gatekeeper chain. Also made `purchases.supplier_id` nullable to match optional-supplier tool design. |
| 2026-08-16 | 📁 Reorganized the project: `mcp/` split into `agents/` (classifier + inventory + shared llm), `models/` (table/view models), `database/` (SQL files + typed `repository.py`), `main.py` (CLI REPL). Agent output models now live beside their agents. Added `rebuild_database()`, sqlite-safe value conversion, a full-run retry + fallback for flaky structured outputs, and conversation history trimmed to the last 10 messages. Test suite moved into `tests/` (pytest, live LLM integration tests). |
