"""Pydantic models mirroring the Inventrio database (schema.sql).

One model per table (plus the four views), with the same constraints the
database enforces:

* CHECK constraints  -> Field bounds / Literal types / validators
* DEFAULT values     -> matching field defaults
* FOREIGN KEYs       -> optional nested relationship fields (read-side only)
* NOT NULL vs NULL   -> required vs Optional fields

Usage notes
-----------
* ``model_validate(row_dict)`` accepts rows straight from ``sqlite3.Row``.
* Nested relationship fields (e.g. ``product.manufacturer``) are for **reads**.
  When writing to the DB, drop them first: ``model_dump(exclude=<rels>)``.
* Dates/times are parsed from SQLite TEXT automatically.

Agent output models (e.g. ``ClassificationResult``, ``InventoryReply``) live
next to their agents in ``inventrio.agents``.
"""

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

#: PK ids: positive integers, optional while a row is not yet inserted.
Id = Annotated[int, Field(gt=0)]


def _validate_indian_phone(v: str) -> str:
    """Accept +91/0-prefixed landlines & mobiles with spaces/dashes; keep original."""
    normalized = re.sub(r"[\s\-()]", "", v)
    if not re.fullmatch(r"\+?91\d{10}", normalized):
        raise ValueError("must be a valid Indian phone number (e.g. '+91 98765 00001')")
    return v


PhoneNumber = Annotated[str, AfterValidator(_validate_indian_phone)]


class InventrioModel(BaseModel):
    """Base config shared by every model: strip whitespace, allow ORM objects."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        from_attributes=True,
    )


# ---------------------------------------------------------------------------
# Catalog tables
# ---------------------------------------------------------------------------


class Manufacturer(InventrioModel):
    """Maps to ``manufacturers``."""

    mid: Id | None = None
    name: Annotated[str, Field(min_length=1, description="Manufacturer name")]
    contact_email: EmailStr | None = None
    contact_phone: PhoneNumber | None = None
    address: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductCategory(InventrioModel):
    """Maps to ``product_categories``."""

    pcid: Id | None = None
    name: Annotated[str, Field(min_length=1)]
    description: str | None = None


class DosageForm(InventrioModel):
    """Maps to ``dosage_forms``."""

    dfid: Id | None = None
    name: Annotated[str, Field(min_length=1)]


class Product(InventrioModel):
    """Maps to ``products`` (brand-level SKU)."""

    pid: Id | None = None
    sku: Annotated[str, Field(min_length=1)]
    brand_name: Annotated[str, Field(min_length=1)]
    generic_name: Annotated[str, Field(min_length=1)]
    manufacturer_id: Id
    category_id: Id | None = None
    dosage_form_id: Id | None = None
    strength: str | None = None
    pack_size: Annotated[int, Field(gt=0)] = 1
    unit: Annotated[str, Field(min_length=1)] = "pack"
    mrp: Annotated[float, Field(ge=0)]
    purchase_price: Annotated[float, Field(ge=0)] = 0
    selling_price: Annotated[float, Field(ge=0)] = 0
    gst_rate: Annotated[float, Field(ge=0, le=100)] | None = None
    requires_prescription: bool = False
    schedule_class: (
        Literal["OTC", "Rx", "Schedule H", "Schedule H1", "Schedule X"] | None
    ) = None
    storage_instructions: str | None = None
    reorder_level: Annotated[int, Field(ge=0)] = 0
    is_active: bool = True
    api_source: str | None = None
    api_code: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Relationships (read-side enrichment)
    manufacturer: Manufacturer | None = None
    category: ProductCategory | None = None
    dosage_form: DosageForm | None = None


class Supplier(InventrioModel):
    """Maps to ``suppliers`` (pharma distributors)."""

    sid: Id | None = None
    name: Annotated[str, Field(min_length=1)]
    contact_person: str | None = None
    phone: PhoneNumber | None = None
    email: EmailStr | None = None
    address: str | None = None
    gstin: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Customer(InventrioModel):
    """Maps to ``customers`` (allergies matter in a pharmacy!)."""

    cid: Id | None = None
    name: Annotated[str, Field(min_length=1)]
    phone: PhoneNumber | None = None
    email: EmailStr | None = None
    address: str | None = None
    age: Annotated[int, Field(gt=0)] | None = None
    allergies: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Stock tables
# ---------------------------------------------------------------------------


class Batch(InventrioModel):
    """Maps to ``batches`` — the physical stock (batch no + expiry required)."""

    bid: Id | None = None
    product_id: Id
    supplier_id: Id | None = None
    batch_number: Annotated[str, Field(min_length=1)]
    mfg_date: date
    expiry_date: date
    quantity: Annotated[int, Field(ge=0)] = 0
    purchase_price: Annotated[float, Field(ge=0)]
    mrp: Annotated[float, Field(ge=0)]
    discount_percent: Annotated[float, Field(ge=0, le=100)] = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Relationships (read-side enrichment)
    product: Product | None = None
    supplier: Supplier | None = None

    @model_validator(mode="after")
    def _expiry_after_mfg(self) -> "Batch":
        if self.expiry_date <= self.mfg_date:
            raise ValueError("expiry_date must be after mfg_date")
        return self


class StockMovement(InventrioModel):
    """Maps to ``stock_movements`` — append-only ledger (audit trail)."""

    smid: Id | None = None
    batch_id: Id
    movement_type: Literal[
        "purchase",
        "sale",
        "adjustment",
        "return_in",
        "return_out",
        "expiry_write_off",
    ]
    quantity: int
    reference_type: Literal["purchase", "sale", "adjustment", "manual"] | None = None
    reference_id: Id | None = None
    notes: str | None = None
    recorded_by: str | None = None
    created_at: datetime | None = None

    # Relationship (read-side enrichment)
    batch: Batch | None = None

    @field_validator("quantity")
    @classmethod
    def _quantity_nonzero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("quantity must be non-zero (+ in / - out)")
        return v


# ---------------------------------------------------------------------------
# Purchase tables
# ---------------------------------------------------------------------------


class Purchase(InventrioModel):
    """Maps to ``purchases`` (stock-in orders)."""

    puid: Id | None = None
    supplier_id: Id | None = None
    invoice_number: str | None = None
    purchase_date: date = Field(default_factory=date.today)
    subtotal: Annotated[float, Field(ge=0)] = 0
    discount_amount: Annotated[float, Field(ge=0)] = 0
    tax_amount: Annotated[float, Field(ge=0)] = 0
    total_amount: Annotated[float, Field(ge=0)] = 0
    status: Literal["pending", "completed", "cancelled"] = "completed"
    notes: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None

    # Relationship (read-side enrichment)
    supplier: Supplier | None = None


class PurchaseItem(InventrioModel):
    """Maps to ``purchase_items``."""

    piid: Id | None = None
    purchase_id: Id
    product_id: Id
    batch_id: Id | None = None
    quantity: Annotated[int, Field(gt=0)]
    unit_price: Annotated[float, Field(ge=0)]
    discount_percent: Annotated[float, Field(ge=0, le=100)] = 0
    total_price: Annotated[float, Field(ge=0)]
    expiry_date: date | None = None

    # Relationships (read-side enrichment)
    product: Product | None = None
    batch: Batch | None = None


# ---------------------------------------------------------------------------
# Sale tables
# ---------------------------------------------------------------------------


class Sale(InventrioModel):
    """Maps to ``sales`` (stock-out bills)."""

    said: Id | None = None
    customer_id: Id | None = None
    sale_date: datetime = Field(default_factory=datetime.now)
    subtotal: Annotated[float, Field(ge=0)] = 0
    discount_amount: Annotated[float, Field(ge=0)] = 0
    tax_amount: Annotated[float, Field(ge=0)] = 0
    total_amount: Annotated[float, Field(ge=0)] = 0
    payment_method: Literal["cash", "upi", "card", "credit", "other"] | None = None
    status: Literal["completed", "refunded", "cancelled"] = "completed"
    notes: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None

    # Relationship (read-side enrichment)
    customer: Customer | None = None


class SaleItem(InventrioModel):
    """Maps to ``sale_items``."""

    siid: Id | None = None
    sale_id: Id
    product_id: Id
    batch_id: Id | None = None
    quantity: Annotated[int, Field(gt=0)]
    unit_price: Annotated[float, Field(ge=0)]
    discount_percent: Annotated[float, Field(ge=0, le=100)] = 0
    total_price: Annotated[float, Field(ge=0)]

    # Relationships (read-side enrichment)
    product: Product | None = None
    batch: Batch | None = None


# ---------------------------------------------------------------------------
# AI agent layer tables
# ---------------------------------------------------------------------------


class AiConversation(InventrioModel):
    """Maps to ``ai_conversations`` (what the user said & what the agent did)."""

    convid: Id | None = None
    user_message: Annotated[str, Field(min_length=1)]
    agent_response: str | None = None
    extracted_intent: str | None = None  # add_stock / sell / check_stock / query ...
    extracted_entities: str | None = None  # JSON text
    status: Literal[
        "processing", "resolved", "awaiting_clarification", "executed", "failed"
    ] = "resolved"
    created_at: datetime | None = None


class PendingClarification(InventrioModel):
    """Maps to ``pending_clarifications`` (follow-up questions the agent asks)."""

    clid: Id | None = None
    conversation_id: Id
    question: Annotated[str, Field(min_length=1)]
    field_name: Annotated[str, Field(min_length=1)]  # quantity / discount / ...
    resolved: bool = False
    resolved_value: str | None = None
    created_at: datetime | None = None
    resolved_at: datetime | None = None

    # Relationship (read-side enrichment)
    conversation: AiConversation | None = None


class ActionLog(InventrioModel):
    """Maps to ``action_log`` (every DB write the agent makes)."""

    alid: Id | None = None
    conversation_id: Id | None = None
    action_type: Annotated[str, Field(min_length=1)]
    target_table: str | None = None
    target_id: Id | None = None
    details: str | None = None  # JSON snapshot of the change
    status: Literal["success", "failed", "rolled_back"] = "success"
    error_message: str | None = None
    created_at: datetime | None = None

    # Relationship (read-side enrichment)
    conversation: AiConversation | None = None


# ---------------------------------------------------------------------------
# View models — structured answers for the AI agent's "check_stock" replies
# ---------------------------------------------------------------------------


class StockSummary(InventrioModel):
    """Maps to ``v_stock_summary`` (per-product totals + LOW/OK flag)."""

    product_id: int
    brand_name: str
    generic_name: str
    strength: str | None = None
    total_stock: int
    reorder_level: int
    stock_status: Literal["LOW", "OK"]
    earliest_expiry: date | None = None
    min_days_to_expiry: float | None = None
    active_batches: int


class CurrentStockBatch(InventrioModel):
    """Maps to ``v_current_stock`` (FEFO-sorted sellable batches)."""

    batch_id: int
    product_id: int
    brand_name: str
    generic_name: str
    strength: str | None = None
    dosage_form: str | None = None
    batch_number: str
    mfg_date: date
    expiry_date: date
    quantity: int
    mrp: float
    discount_percent: float
    requires_prescription: bool
    days_to_expiry: float


class ExpiringBatch(InventrioModel):
    """Maps to ``v_expiring_soon`` (stock expiring within 90 days)."""

    bid: int
    brand_name: str
    generic_name: str
    batch_number: str
    quantity: int
    expiry_date: date
    days_to_expiry: float


class DailySalesRow(InventrioModel):
    """Maps to ``v_daily_sales`` (day-wise revenue at a glance)."""

    day: date
    invoices: int
    subtotal: float
    discounts: float
    tax: float
    revenue: float
