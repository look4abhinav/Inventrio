"""CLI entrypoint: chat with the Inventrio pharmacy assistant.

Pipeline: classifier_agent (gatekeeper) -> inventory_agent (worker).
Run with:  uv run python -m inventrio.main
"""

from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage

from inventrio.agents import classifier_agent, run_chat
from inventrio.database import repository as db

FALLBACK_REPLY = "Sorry, I got confused while processing that — could you rephrase it?"


def chat_turn(
    message: str, history: list[ModelMessage], conv_id: int
) -> tuple[str, str]:
    """Run one user message through the pipeline.

    Returns (reply_text, conversation_status).
    """
    try:
        verdict = classifier_agent.run_sync(message)
    except UnexpectedModelBehavior:
        db.update_conversation(conv_id, FALLBACK_REPLY, "failed")
        return FALLBACK_REPLY, "failed"
    if not verdict.output.is_related:
        reply_text = f"That's outside what I can help with: {verdict.output.reason}"
        db.update_conversation(conv_id, reply_text, "resolved")
        return reply_text, "resolved"

    try:
        reply = run_chat(message, history, conv_id)
    except UnexpectedModelBehavior:
        db.update_conversation(conv_id, FALLBACK_REPLY, "failed")
        return FALLBACK_REPLY, "failed"

    if db.open_clarifications(conv_id):
        status = "awaiting_clarification"
    elif db.has_actions(conv_id):
        status = "executed"
    else:
        status = "resolved"
    db.update_conversation(conv_id, reply.reply, status)
    return reply.reply, status


def main() -> None:
    history: list[ModelMessage] = []
    print("💊 Inventrio — pharmacy inventory assistant")
    print("   (type 'quit' to exit)\n")
    while True:
        try:
            message = input("👤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not message:
            continue
        if message.lower() in {"quit", "exit", "q"}:
            break

        conv_id = db.save_conversation(message)
        reply_text, _status = chat_turn(message, history, conv_id)
        print(f"🤖 Agent: {reply_text}\n")


if __name__ == "__main__":
    main()
