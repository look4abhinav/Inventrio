"""Typed SQLite layer used by the inventory agent's tools.

Every function reads/writes rows through the Pydantic models in
``inventrio.models``, so the agent layer never touches the database with
raw, unvalidated data.

Stock rule that lives here (and only here):
* purchases INSERT a batch + a positive ``stock_movements`` row
* sales INSERT negative ``stock_movements`` rows (FEFO order)
* the ``trg_movements_update_batch`` trigger keeps ``batches.quantity``
  in sync — this module never writes quantities directly.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from inventrio.models.tables import (
    ActionLog,
    Batch,
    Customer,
    ExpiringBatch,
    Product,
    Purchase,
    PurchaseItem,
    Sale,
    SaleItem,
    StockMovement,
    StockSummary,
    Supplier,
)

DB_PATH = Path(__file__).parent / "inventrio.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
SEED_PATH = Path(__file__).parent / "seed.sql"


class InventoryError(ValueError):
    """Raised when a requested operation cannot be performed on the inventory."""


def _validate(model_cls, payload):
    """Validate through a Pydantic model, surfacing friendly errors."""
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        raise InventoryError(str(exc)) from exc


def _to_sql(value):
    """Convert Python values to SQLite-safe values (TEXT dates, INT bools)."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return int(value)
    return value


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def rebuild_database() -> None:
    """Drop everything and re-apply schema.sql + seed.sql (fresh dummy data)."""
    DB_PATH.unlink(missing_ok=True)
    with connect() as con:
        con.executescript(SCHEMA_PATH.read_text())
        con.executescript(SEED_PATH.read_text())


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def search_products(query: str) -> list[Product]:
    """Token-wise AND search: every word of the query must match brand,
    generic name or SKU (e.g. 'Electral ORS' matches brand + generic)."""
    tokens = [t for t in query.strip().split() if t]
    if not tokens:
        return []
    clauses = []
    params = []
    for token in tokens:
        pattern = f"%{token}%"
        clauses.append("(brand_name LIKE ? OR generic_name LIKE ? OR sku LIKE ?)")
        params.extend((pattern, pattern, pattern))
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM products WHERE is_active = 1 AND "
            + " AND ".join(clauses)
            + " ORDER BY brand_name LIMIT 10",
            params,
        ).fetchall()
    return [Product.model_validate(dict(row)) for row in rows]


def get_product(product_id: int) -> Product | None:
    with connect() as con:
        row = con.execute(
            "SELECT * FROM products WHERE pid = ?", (product_id,)
        ).fetchone()
    return Product.model_validate(dict(row)) if row else None


def stock_summary(brand_query: str | None = None) -> list[StockSummary]:
    with connect() as con:
        if brand_query:
            pattern = f"%{brand_query.strip()}%"
            rows = con.execute(
                """SELECT * FROM v_stock_summary
                   WHERE brand_name LIKE ? OR generic_name LIKE ?
                   ORDER BY brand_name""",
                (pattern, pattern),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM v_stock_summary ORDER BY stock_status DESC, brand_name"
            ).fetchall()
    return [StockSummary.model_validate(dict(row)) for row in rows]


def expiring_batches(days: int = 90) -> list[ExpiringBatch]:
    with connect() as con:
        rows = con.execute(
            """SELECT * FROM v_expiring_soon
               WHERE days_to_expiry <= ?
               ORDER BY expiry_date""",
            (days,),
        ).fetchall()
    return [ExpiringBatch.model_validate(dict(row)) for row in rows]


def list_suppliers() -> list[Supplier]:
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM suppliers WHERE is_active = 1 ORDER BY name"
        ).fetchall()
    return [Supplier.model_validate(dict(row)) for row in rows]


def _fefo_batches(product_id: int) -> list[Batch]:
    """All in-stock batches of a product, oldest-expiry first."""
    with connect() as con:
        rows = con.execute(
            """SELECT * FROM batches
               WHERE product_id = ? AND quantity > 0
               ORDER BY expiry_date ASC""",
            (product_id,),
        ).fetchall()
    return [Batch.model_validate(dict(row)) for row in rows]


def _find_or_create_customer(con: sqlite3.Connection, name: str) -> int:
    row = con.execute(
        "SELECT cid FROM customers WHERE lower(name) = lower(?)", (name.strip(),)
    ).fetchone()
    if row:
        return row["cid"]
    customer = Customer.model_validate({"name": name.strip()})
    cur = con.execute(
        """INSERT INTO customers (name, created_at, updated_at)
           VALUES (?, datetime('now'), datetime('now'))""",
        (customer.name,),
    )
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Writes — purchases (add stock)
# ---------------------------------------------------------------------------


def record_purchase(
    *,
    product_id: int,
    quantity: int,
    batch_number: str,
    mfg_date: date,
    expiry_date: date,
    unit_price: float | None = None,
    supplier_id: int | None = None,
    invoice_number: str | None = None,
    discount_percent: float = 0.0,
    created_by: str = "inventory_agent",
    conversation_id: int | None = None,
) -> dict:
    """Record a stock-in purchase: purchase + item + batch + ledger movement."""

    if quantity <= 0:
        raise InventoryError(f"Quantity must be positive, got {quantity}.")

    product = get_product(product_id)
    if product is None:
        raise InventoryError(f"No active product with id {product_id}.")

    # Validate through the Batch model (mirrors the DB CHECK constraints).
    batch = _validate(
        Batch,
        {
            "product_id": product_id,
            "supplier_id": supplier_id,
            "batch_number": batch_number.strip(),
            "mfg_date": mfg_date,
            "expiry_date": expiry_date,
            "quantity": 0,  # filled by the ledger trigger below
            "purchase_price": unit_price
            if unit_price is not None
            else product.purchase_price,
            "mrp": product.mrp,
            "discount_percent": discount_percent,
        },
    )

    subtotal = round(quantity * batch.purchase_price, 2)
    discount_amount = round(subtotal * discount_percent / 100, 2)
    total = round(subtotal - discount_amount, 2)
    purchase = _validate(
        Purchase,
        {
            "supplier_id": supplier_id,
            "invoice_number": invoice_number,
            "subtotal": subtotal,
            "discount_amount": discount_amount,
            "tax_amount": 0.0,
            "total_amount": total,
            "status": "completed",
            "notes": "Recorded by AI agent",
            "created_by": created_by,
        },
    )

    with connect() as con:
        cur = con.execute(
            """INSERT INTO purchases
               (supplier_id, invoice_number, subtotal, discount_amount,
                tax_amount, total_amount, status, notes, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                purchase.supplier_id,
                purchase.invoice_number,
                purchase.subtotal,
                purchase.discount_amount,
                purchase.tax_amount,
                purchase.total_amount,
                purchase.status,
                purchase.notes,
                purchase.created_by,
            ),
        )
        puid = cur.lastrowid

        existing = con.execute(
            "SELECT bid FROM batches WHERE product_id = ? AND batch_number = ?",
            (product_id, batch.batch_number),
        ).fetchone()
        if existing:
            bid = existing["bid"]
        else:
            values = batch.model_dump(
                exclude={"bid", "product", "supplier", "created_at", "updated_at"}
            )
            columns = ", ".join(values)
            cur = con.execute(
                f"INSERT INTO batches ({columns}) VALUES ({', '.join('?' * len(values))})",
                tuple(_to_sql(v) for v in values.values()),
            )
            bid = cur.lastrowid

        item = _validate(
            PurchaseItem,
            {
                "purchase_id": puid,
                "product_id": product_id,
                "batch_id": bid,
                "quantity": quantity,
                "unit_price": batch.purchase_price,
                "discount_percent": discount_percent,
                "total_price": subtotal,
                "expiry_date": expiry_date,
            },
        )
        values = item.model_dump(exclude={"piid", "product", "batch"})
        columns = ", ".join(values)
        con.execute(
            f"INSERT INTO purchase_items ({columns}) VALUES ({', '.join('?' * len(values))})",
            tuple(_to_sql(v) for v in values.values()),
        )

        movement = _validate(
            StockMovement,
            {
                "batch_id": bid,
                "movement_type": "purchase",
                "quantity": quantity,
                "reference_type": "purchase",
                "reference_id": puid,
                "notes": "Stock-in via AI agent",
                "recorded_by": created_by,
            },
        )
        values = movement.model_dump(exclude={"smid", "batch", "created_at"})
        columns = ", ".join(values)
        con.execute(
            f"INSERT INTO stock_movements ({columns}) VALUES ({', '.join('?' * len(values))})",
            tuple(_to_sql(v) for v in values.values()),
        )
        # ↑ trg_movements_update_batch bumps batches.quantity

    log_action(
        conversation_id,
        "purchase_recorded",
        "purchases",
        puid,
        json.dumps(
            {
                "product": product.brand_name,
                "quantity": quantity,
                "batch_number": batch.batch_number,
                "expiry_date": expiry_date.isoformat(),
                "total": total,
            }
        ),
    )
    return {
        "purchase_id": puid,
        "batch_id": bid,
        "brand": product.brand_name,
        "batch_number": batch.batch_number,
        "quantity": quantity,
        "unit_price": batch.purchase_price,
        "expiry_date": expiry_date.isoformat(),
        "discount_percent": discount_percent,
        "total": total,
    }


# ---------------------------------------------------------------------------
# Writes — sales (sell stock, FEFO)
# ---------------------------------------------------------------------------


def record_sale(
    *,
    product_id: int,
    quantity: int,
    unit_price: float | None = None,
    customer_name: str | None = None,
    payment_method: str | None = None,
    discount_percent: float = 0.0,
    created_by: str = "inventory_agent",
    conversation_id: int | None = None,
) -> dict:
    """Record a sale, consuming stock from the oldest-expiry batches first."""

    if quantity <= 0:
        raise InventoryError(f"Quantity must be positive, got {quantity}.")

    product = get_product(product_id)
    if product is None:
        raise InventoryError(f"No active product with id {product_id}.")

    batches = _fefo_batches(product_id)
    total_stock = sum(b.quantity for b in batches)
    if total_stock < quantity:
        raise InventoryError(
            f"Not enough stock of {product.brand_name}: only {total_stock} "
            f"available across all batches."
        )

    price = unit_price if unit_price is not None else product.selling_price
    sale = _validate(
        Sale,
        {
            "customer_id": None,
            "subtotal": 0.0,  # recomputed below
            "discount_amount": 0.0,
            "tax_amount": 0.0,
            "total_amount": 0.0,
            "payment_method": payment_method,
            "status": "completed",
            "notes": "Recorded by AI agent",
            "created_by": created_by,
        },
    )

    # Split the quantity across batches in FEFO order.
    remaining = quantity
    picked: list[tuple[int, int]] = []  # (batch_id, units)
    for batch in batches:
        take = min(batch.quantity, remaining)
        if take <= 0:
            continue
        picked.append((batch.bid, take))
        remaining -= take
        if remaining == 0:
            break

    subtotal = round(quantity * price, 2)
    discount_amount = round(subtotal * discount_percent / 100, 2)
    total = round(subtotal - discount_amount, 2)

    with connect() as con:
        customer_id = (
            _find_or_create_customer(con, customer_name) if customer_name else None
        )
        cur = con.execute(
            """INSERT INTO sales
               (customer_id, subtotal, discount_amount, tax_amount,
                total_amount, payment_method, status, notes, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                customer_id,
                subtotal,
                discount_amount,
                0.0,
                total,
                sale.payment_method,
                sale.status,
                sale.notes,
                sale.created_by,
            ),
        )
        said = cur.lastrowid

        for bid, units in picked:
            line = _validate(
                SaleItem,
                {
                    "sale_id": said,
                    "product_id": product_id,
                    "batch_id": bid,
                    "quantity": units,
                    "unit_price": price,
                    "discount_percent": discount_percent,
                    "total_price": round(units * price, 2),
                },
            )
            values = line.model_dump(exclude={"siid", "product", "batch"})
            columns = ", ".join(values)
            con.execute(
                f"INSERT INTO sale_items ({columns}) VALUES ({', '.join('?' * len(values))})",
                tuple(_to_sql(v) for v in values.values()),
            )

            movement = _validate(
                StockMovement,
                {
                    "batch_id": bid,
                    "movement_type": "sale",
                    "quantity": -units,
                    "reference_type": "sale",
                    "reference_id": said,
                    "notes": "Sale via AI agent",
                    "recorded_by": created_by,
                },
            )
            values = movement.model_dump(exclude={"smid", "batch", "created_at"})
            columns = ", ".join(values)
            con.execute(
                f"INSERT INTO stock_movements ({columns}) VALUES ({', '.join('?' * len(values))})",
                tuple(_to_sql(v) for v in values.values()),
            )
            # ↑ trg_movements_update_batch decrements batches.quantity

    log_action(
        conversation_id,
        "sale_recorded",
        "sales",
        said,
        json.dumps(
            {
                "product": product.brand_name,
                "quantity": quantity,
                "customer": customer_name,
                "payment_method": payment_method,
                "total": total,
            }
        ),
    )
    return {
        "sale_id": said,
        "brand": product.brand_name,
        "quantity": quantity,
        "unit_price": price,
        "total": total,
        "customer": customer_name,
        "payment_method": payment_method,
        "requires_prescription": bool(product.requires_prescription),
        "batches_used": [b for b, _ in picked],
        "stock_left": total_stock - quantity,
    }


# ---------------------------------------------------------------------------
# AI conversation layer
# ---------------------------------------------------------------------------


def save_conversation(user_message: str) -> int:
    with connect() as con:
        cur = con.execute(
            "INSERT INTO ai_conversations (user_message, status) VALUES (?, 'processing')",
            (user_message,),
        )
        return cur.lastrowid


def update_conversation(conv_id: int, agent_response: str, status: str) -> None:
    with connect() as con:
        con.execute(
            "UPDATE ai_conversations SET agent_response = ?, status = ? WHERE convid = ?",
            (agent_response, status, conv_id),
        )


def add_clarification(conv_id: int, question: str, field_name: str) -> int:
    with connect() as con:
        cur = con.execute(
            """INSERT INTO pending_clarifications (conversation_id, question, field_name)
               VALUES (?, ?, ?)""",
            (conv_id, question, field_name),
        )
        return cur.lastrowid


def resolve_clarification(conv_id: int, answer: str) -> str | None:
    """Mark the oldest unanswered question for this conversation as answered."""
    with connect() as con:
        row = con.execute(
            """SELECT clid, field_name FROM pending_clarifications
               WHERE conversation_id = ? AND resolved = 0
               ORDER BY clid ASC LIMIT 1""",
            (conv_id,),
        ).fetchone()
        if row is None:
            return None
        con.execute(
            """UPDATE pending_clarifications
               SET resolved = 1, resolved_value = ?, resolved_at = datetime('now')
               WHERE clid = ?""",
            (answer, row["clid"]),
        )
        return row["field_name"]


def open_clarifications(conv_id: int) -> list[dict]:
    with connect() as con:
        rows = con.execute(
            """SELECT question, field_name FROM pending_clarifications
               WHERE conversation_id = ? AND resolved = 0
               ORDER BY clid""",
            (conv_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def has_actions(conv_id: int) -> bool:
    with connect() as con:
        row = con.execute(
            """SELECT COUNT(*) AS n FROM action_log
               WHERE conversation_id = ? AND status = 'success'""",
            (conv_id,),
        ).fetchone()
    return bool(row["n"])


def log_action(
    conversation_id: int | None,
    action_type: str,
    target_table: str | None = None,
    target_id: int | None = None,
    details: str | None = None,
    status: str = "success",
    error_message: str | None = None,
) -> None:
    entry = ActionLog.model_validate(
        {
            "conversation_id": conversation_id,
            "action_type": action_type,
            "target_table": target_table,
            "target_id": target_id,
            "details": details,
            "status": status,
            "error_message": error_message,
        }
    )
    with connect() as con:
        con.execute(
            """INSERT INTO action_log
               (conversation_id, action_type, target_table, target_id,
                details, status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.conversation_id,
                entry.action_type,
                entry.target_table,
                entry.target_id,
                entry.details,
                entry.status,
                entry.error_message,
            ),
        )
