"""The inventory agent: pharmacy stock management via natural conversation.

Pipeline position (see ``classifier.py``):
    user -> classifier_agent (relevant?) -> inventory_agent (this file)

This agent owns every database write and the clarification loop:

* tools read/write the inventory through ``database/repository.py``
  (never raw SQL)
* when required info is missing, the agent sets ``clarification`` in its
  structured output (``InventoryReply``); the caller persists it to
  ``pending_clarifications`` — this makes the ask-back loop deterministic
* on the next turn, dynamic instructions re-surface the unanswered
  questions, and the ``resolve_clarification`` tool records the user's
  answer so the agent can continue the pending action
* ``run_chat`` keeps the conversation context trimmed to the last 10
  messages

Run the demo:  uv run python -m inventrio.main
"""

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage

from inventrio.agents.llm import chat_model
from inventrio.database import repository as db
from inventrio.models.tables import ExpiringBatch, Product, StockSummary, Supplier

#: How many chat messages (user + assistant) to keep in the session history.
HISTORY_LIMIT = 10
#: Full-run attempts when the model emits an invalid structured output.
MAX_RUN_ATTEMPTS = 2


class InventoryReply(BaseModel):
    """Structured output of the inventory agent.

    ``clarification`` is the deterministic mechanism for the "ask back" loop:
    whenever the agent needs information from the user, it sets this field,
    and the caller persists it to ``pending_clarifications``.
    """

    reply: Annotated[
        str,
        Field(description="The short message to show the user (their language)."),
    ]
    clarification: Annotated[
        str | None,
        Field(
            description=(
                "The question to ask the user when required information is "
                "missing. Null if nothing is needed."
            ),
        ),
    ] = None
    clarification_field: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated names of the missing fields, e.g. "
                "'batch_number,expiry_date'. Null if clarification is null."
            ),
        ),
    ] = None


@dataclass
class InventoryDeps:
    """Runtime context injected into every tool call."""

    conversation_id: int
    created_by: str = "inventory_agent"


BASE_INSTRUCTIONS = """\
You are Inventrio, the friendly inventory assistant of a pharmacy. You help \
the shopkeeper manage stock through natural conversation, in English, Hindi \
or Hinglish — reply in the language the user used.

WHAT YOU CAN DO
- check_stock: how much stock a medicine has, broken down by batch (FEFO
  order) with reorder warnings
- check_expiring: batches expiring soon or already expired
- record_purchase (add stock): needs product, quantity, batch number,
  manufacturing date and expiry date; supplier, unit price, invoice number
  and discount are optional
- record_sale (sell): needs product and quantity; price, customer name and
  payment method are optional
- resolve_clarification: record the user's answer to a pending question

YOUR FINAL ANSWER IS STRUCTURED with three fields:
- reply: the short message you show the user, in their language
- clarification: if the user must provide something before you can act,
  put your question here; otherwise null
- clarification_field: comma-separated names of the missing fields
  (e.g. 'batch_number,expiry_date'), or null

HARD RULES
1. NEVER invent data the user did not provide — especially batch numbers,
   expiry dates, prices and quantities.
2. Whenever required information is missing, do NOT record anything.
   End your turn with `clarification` set to the question you need answered
   and `clarification_field` naming the missing fields. The reply field
   should be a friendly version of the same question.
   Only set `clarification` when the user's CURRENT request is blocked
   without it. Do NOT set it when merely answering a question or offering
   future help.
3. Medicines carry expiry dates by law. A purchase without a batch number
   and expiry date must NOT be recorded.
4. NEVER ask the user for OPTIONAL fields. For purchases, only the product,
   quantity, batch number, manufacturing date and expiry date are required.
   Supplier, unit price, invoice number and discount are optional — if the
   user has not mentioned them, call record_purchase WITHOUT them (null).
   Do NOT list suppliers or ask which supplier to use.
   Example: "Add 20 Electral, batch ELC-1, mfg 2026-07-01, expiry 2027-06-30"
   -> call record_purchase directly with those values, no supplier, and
   confirm to the user.
5. Always call search_products first when the user mentions a medicine.
   If nothing matches, ask the user to confirm the name — do not guess ids.
6. When selling, stock is consumed FEFO (first expiry, first out). If there
   is not enough stock, tell the user how much is left and do not record
   anything.
7. If a product requires a prescription, mention it when selling.
8. If a tool raises an error, respect it: explain it to the user or ask for
   the missing information. Never retry with invented values.
9. After any database change, confirm with a short friendly summary: what
   was added or sold, batch number, expiry, prices and totals.
10. If the user's message answers a previously asked question, first call
    resolve_clarification with their answer, then continue the pending
    action you were working on.
"""


def dynamic_instructions(ctx: RunContext[InventoryDeps]) -> str:
    """Re-surface unanswered clarification questions on every turn."""
    clarifications = db.open_clarifications(ctx.deps.conversation_id)
    if not clarifications:
        return BASE_INSTRUCTIONS
    lines = "\n".join(
        f"- Q: {c['question']} (field: {c['field_name']})" for c in clarifications
    )
    return (
        BASE_INSTRUCTIONS
        + "\n\nUNANSWERED QUESTIONS FOR THIS CONVERSATION\n"
        + lines
        + "\n\nIf the user's message answers any of these, call "
        "resolve_clarification with the answer, then continue the pending "
        "action you were working on."
    )


inventory_agent = Agent(
    chat_model,
    name="inventory",
    instructions=dynamic_instructions,
    deps_type=InventoryDeps,
    output_type=InventoryReply,
    model_settings={"temperature": 0.1},
    retries={"output": 3, "tools": 2},
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@inventory_agent.tool
def search_products(ctx: RunContext[InventoryDeps], query: str) -> list[Product]:
    """Find products by brand name, generic name or SKU.

    ALWAYS call this first when the user mentions a medicine, to get the
    correct product_id.
    """
    results = db.search_products(query)
    if not results:
        raise ValueError(
            f"No product matches '{query}'. Ask the user to confirm the "
            "medicine name or spelling."
        )
    return results


@inventory_agent.tool
def check_stock(
    ctx: RunContext[InventoryDeps], brand_query: str | None = None
) -> list[StockSummary]:
    """Return current stock per product (totals, reorder level, LOW/OK flag).

    Pass a brand_query to filter by brand or generic name, or omit it to get
    everything, with low-stock items first.
    """
    return db.stock_summary(brand_query)


@inventory_agent.tool
def check_expiring(
    ctx: RunContext[InventoryDeps], days: int = 90
) -> list[ExpiringBatch]:
    """Return batches expiring within the next `days` (already-expired first)."""
    return db.expiring_batches(days)


@inventory_agent.tool
def list_suppliers(ctx: RunContext[InventoryDeps]) -> list[Supplier]:
    """Return the active suppliers (distributors), with their ids."""
    return db.list_suppliers()


@inventory_agent.tool
def record_purchase(
    ctx: RunContext[InventoryDeps],
    product_id: int,
    quantity: int,
    batch_number: str | None,
    mfg_date: date | None,
    expiry_date: date | None,
    unit_price: float | None = None,
    supplier_id: int | None = None,
    invoice_number: str | None = None,
    discount_percent: float = 0.0,
) -> str:
    """Record a stock-in purchase (add stock).

    batch_number, mfg_date and expiry_date are REQUIRED: if the user has not
    provided them, do not call this tool — end your turn with `clarification`
    set instead.
    """
    if batch_number is None or mfg_date is None or expiry_date is None:
        raise ValueError(
            "Batch number, manufacturing date and expiry date are required to "
            "add stock. Ask the user for the missing details — never invent "
            "them."
        )
    result = db.record_purchase(
        product_id=product_id,
        quantity=quantity,
        batch_number=batch_number,
        mfg_date=mfg_date,
        expiry_date=expiry_date,
        unit_price=unit_price,
        supplier_id=supplier_id,
        invoice_number=invoice_number,
        discount_percent=discount_percent,
        created_by=ctx.deps.created_by,
        conversation_id=ctx.deps.conversation_id,
    )
    return (
        f"Added {result['quantity']} units of {result['brand']} "
        f"(batch {result['batch_number']}, expires {result['expiry_date']}) "
        f"at {result['unit_price']:.2f} per unit, "
        f"discount {result['discount_percent']:.1f}%, total {result['total']:.2f}. "
        f"Purchase id {result['purchase_id']}."
    )


@inventory_agent.tool
def record_sale(
    ctx: RunContext[InventoryDeps],
    product_id: int,
    quantity: int,
    unit_price: float | None = None,
    customer_name: str | None = None,
    payment_method: Literal["cash", "upi", "card", "credit", "other"] | None = None,
    discount_percent: float = 0.0,
) -> str:
    """Record a sale (sell stock). Stock is consumed FEFO, oldest expiry first."""
    result = db.record_sale(
        product_id=product_id,
        quantity=quantity,
        unit_price=unit_price,
        customer_name=customer_name,
        payment_method=payment_method,
        discount_percent=discount_percent,
        created_by=ctx.deps.created_by,
        conversation_id=ctx.deps.conversation_id,
    )
    rx_note = " Note: prescription required." if result["requires_prescription"] else ""
    return (
        f"Sold {result['quantity']} units of {result['brand']} for "
        f"{result['total']:.2f}"
        + (f" to {result['customer']}" if result["customer"] else "")
        + (f" via {result['payment_method']}" if result["payment_method"] else "")
        + f". {result['stock_left']} units left.{rx_note} Sale id {result['sale_id']}."
    )


@inventory_agent.tool
def resolve_clarification(ctx: RunContext[InventoryDeps], answer: str) -> str:
    """Mark the oldest unanswered question as answered with `answer`.

    Call this when the user's message provides a previously requested
    detail, then continue the pending action.
    """
    field = db.resolve_clarification(ctx.deps.conversation_id, answer)
    if field is None:
        return "There are no unanswered questions for this conversation."
    return f"Recorded answer for '{field}': {answer}. Now continue the pending action."


# ---------------------------------------------------------------------------
# Chat runner
# ---------------------------------------------------------------------------


def run_chat(
    message: str, history: list[ModelMessage], conversation_id: int
) -> InventoryReply:
    """Run one turn, persist any clarification, keep history at 10 messages."""
    for attempt in range(MAX_RUN_ATTEMPTS):
        try:
            result = inventory_agent.run_sync(
                message,
                deps=InventoryDeps(conversation_id=conversation_id),
                message_history=history,
            )
            break
        except UnexpectedModelBehavior:
            if attempt == MAX_RUN_ATTEMPTS - 1:
                raise
    history.extend(result.new_messages())
    history[:] = history[-HISTORY_LIMIT:]
    reply = result.output
    clarification = (reply.clarification or "").strip()
    if clarification and clarification.lower() not in {"null", "none", "na", "n/a"}:
        db.add_clarification(
            conversation_id,
            clarification,
            reply.clarification_field or "missing_info",
        )
    return reply
