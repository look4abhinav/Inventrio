"""End-to-end test of the agent pipeline against a fresh seeded database.

Requires a working .env (OPENCODE_BASE_URL / OPENCODE_API_KEY) and network
access to the LLM — these are live integration tests.
"""

from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage

from inventrio.agents import classifier_agent, run_chat
from inventrio.database import repository as db


def turn(message: str, history: list[ModelMessage], conv_id: int) -> str:
    try:
        verdict = classifier_agent.run_sync(message)
    except UnexpectedModelBehavior:
        db.update_conversation(conv_id, "FALLBACK", "failed")
        return "[failed] FALLBACK"
    if not verdict.output.is_related:
        reply = f"GATEKEEPER: {verdict.output.reason}"
        db.update_conversation(conv_id, reply, "resolved")
        return reply
    try:
        reply = run_chat(message, history, conv_id)
    except UnexpectedModelBehavior:
        db.update_conversation(conv_id, "FALLBACK", "failed")
        return "[failed] FALLBACK"
    if db.open_clarifications(conv_id):
        status = "awaiting_clarification"
    elif db.has_actions(conv_id):
        status = "executed"
    else:
        status = "resolved"
    db.update_conversation(conv_id, reply.reply, status)
    return f"[{status}] {reply.reply}"


def setup_function() -> None:
    """Fresh database before every test."""
    db.rebuild_database()


def test_ask_back_then_record_purchase() -> None:
    history: list[ModelMessage] = []
    conv_id = db.save_conversation("Add 20 packets of ORS - Electral")
    first = turn("Add 20 packets of ORS - Electral", history, conv_id)
    assert first.startswith("[awaiting_clarification]"), first
    assert db.open_clarifications(conv_id), "clarification must be persisted"

    second = turn(
        "Batch ELC-2026-10, manufactured 2026-07-01, expires 2027-06-30, 5% discount",
        history,
        conv_id,
    )
    assert second.startswith("[executed]"), second
    row = (
        db.connect()
        .execute("SELECT quantity FROM batches WHERE batch_number = 'ELC-2026-10'")
        .fetchone()
    )
    assert row is not None and row["quantity"] == 20


def test_check_stock_answers_without_clarification() -> None:
    history: list[ModelMessage] = []
    conv_id = db.save_conversation("How much Dolo 650 stock is left?")
    reply = turn("How much Dolo 650 stock is left?", history, conv_id)
    assert reply.startswith("[resolved]"), reply
    assert not db.open_clarifications(conv_id)


def test_sale_consumes_stock() -> None:
    history: list[ModelMessage] = []
    conv_id = db.save_conversation("Sell 5 strips of Dolo 650 to Ramesh, card payment")
    reply = turn("Sell 5 strips of Dolo 650 to Ramesh, card payment", history, conv_id)
    assert reply.startswith("[executed]"), reply
    row = (
        db.connect()
        .execute("SELECT quantity FROM batches WHERE batch_number = 'DLO-2026-05'")
        .fetchone()
    )
    assert row["quantity"] == 5  # 10 seeded - 5 sold


def test_oversell_is_refused() -> None:
    history: list[ModelMessage] = []
    conv_id = db.save_conversation("Sell 100 sachets of Electral")
    reply = turn("Sell 100 sachets of Electral", history, conv_id)
    assert not reply.startswith("[executed]"), reply
    count = db.connect().execute("SELECT COUNT(*) AS n FROM sales").fetchone()["n"]
    assert count == 4  # only the seeded sales exist


def test_gatekeeper_rejects_off_topic() -> None:
    history: list[ModelMessage] = []
    conv_id = db.save_conversation("Which is the latest marvel movie?")
    reply = turn("Which is the latest marvel movie?", history, conv_id)
    assert reply.startswith("GATEKEEPER"), reply


def test_history_is_trimmed_to_ten_messages() -> None:
    history: list[ModelMessage] = []
    conv_id = db.save_conversation("How much Dolo 650 stock is left?")
    for _ in range(3):
        turn("How much Dolo 650 stock is left?", history, conv_id)
    assert len(history) <= 10, f"history grew to {len(history)} messages"
