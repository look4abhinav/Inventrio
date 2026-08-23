# Inventrio — Agent Instructions

## Task tracking (important!)

- **TASKS.md** is the single source of truth for feature status, roadmap and changelog.
- Whenever work starts, progresses, or completes on a task:
  1. Update its status in `TASKS.md` (✅ / 🚧 / 💭) and add a changelog row.
  2. Update the "✨ Current State" section in `README.md` so it stays in sync.
- Never let the README's "Current State" drift from TASKS.md.

## Database

- Schema: `src/inventrio/database/schema.sql` · Seed: `src/inventrio/database/seed.sql`
- Rebuild & verify after schema changes:
  ```bash
  sqlite3 src/inventrio/database/inventrio.db < src/inventrio/database/schema.sql
  sqlite3 src/inventrio/database/inventrio.db < src/inventrio/database/seed.sql
  ```
- The `inventrio.db` file is gitignored (regenerable via the two commands above).

## Project facts

- Pydantic AI learning project: AI agent for pharmacy inventory management.
- Python 3.13+, managed with `uv`.
- Stock quantities live in `batches` and are driven by the `stock_movements` ledger trigger — never update `batches.quantity` directly.
- Column naming convention: primary keys use short prefixed names (`mid`, `pid`, `bid`, `said`, …); foreign keys stay descriptive `<entity>_id` (`product_id`, `supplier_id`, …).

## Project layout

- `src/inventrio/agents/` — all AI agents: `classifier.py` (gatekeeper), `inventory.py` (worker + tools + clarification loop), `llm.py` (shared chat model). Agent output models live beside their agent.
- `src/inventrio/models/` — Pydantic models for DB tables & views (`tables.py`).
- `src/inventrio/database/` — SQL files (`schema.sql`, `seed.sql`, `queries.sql`) + typed `repository.py` (agents never write raw SQL outside it).
- `src/inventrio/main.py` — CLI chat entrypoint.
- `tests/` — pytest integration tests (hit the real LLM, need `.env` + network).

## Tests

- `uv run pytest tests/ -v` — live end-to-end agent tests; each test rebuilds the DB from seed.
