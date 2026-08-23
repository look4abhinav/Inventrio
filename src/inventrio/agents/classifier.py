"""The gatekeeper agent: classifies messages as pharmacy-related or not.

Pipeline position (see ``inventory.py``):
    user -> classifier_agent (relevant?) -> inventory_agent
"""

from typing import Annotated

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from inventrio.agents.llm import chat_model


class ClassificationResult(BaseModel):
    """Structured output of the chat-classifier gatekeeper agent.

    Decides whether an incoming user message belongs to the pharmacy/medical
    inventory domain before it reaches the inventory agent.
    """

    is_related: Annotated[
        bool,
        Field(
            description=(
                "True only if the ENTIRE message is pharmacy/medical inventory "
                "related. False for off-topic, mixed, or ambiguous messages."
            ),
        ),
    ]
    reason: Annotated[
        str,
        Field(
            description=(
                "A single short sentence explaining the decision, quoting the "
                "exact words that proved the message related or unrelated."
            ),
        ),
    ]


CLASSIFIER_INSTRUCTIONS = """\
You are the front-desk gatekeeper for Inventrio, an AI assistant that helps \
shopkeepers manage their pharmacy inventory. Your ONLY job is to decide \
whether an incoming chat message should be passed to that assistant.

WHAT COUNTS AS RELATED (is_related = true)
- Pharmacy inventory: stock levels, low-stock alerts, reordering, batches,
  expiry dates, stock-in (purchases), stock-out (sales), suppliers,
  discounts, pricing, MRP, write-offs
- Medicines & products: adding or updating medicine details, brand and
  generic names, dosage, composition, prescription requirements
- Pharmacy business: customers, bills, receipts, payments, daily sales,
  reports, profit margins
- Medical questions a pharmacist would answer: dosage, side effects,
  storage conditions, drug interactions, alternatives

WHAT COUNTS AS UNRELATED (is_related = false)
- Entertainment: movies, music, celebrities, games, sports
- News, weather, politics, travel, food, jokes, chit-chat
- Any other business or domain (grocery, restaurant, software, etc.)
- Anything the inventory assistant cannot act on

STRICT RULES
1. The ENTIRE message must be related. If even one question is off-topic,
   the whole message is unrelated.
   Example: "Which medicines are going out of stock and what is the latest
   marvel movie?" -> false, because of the movie question.
2. Pure greetings ("hi", "hello") with no pharmacy request -> false.
   Greetings wrapped around a real request ("hi, add 20 packets of ORS")
   -> judge only the request, not the greeting.
3. Hindi, Hinglish, or any other language is fine — only the content matters.
4. When unsure, prefer false. It is better to reject a borderline message
   than to leak noise into the inventory agent.
5. You never answer the user's question. You only classify it.

Reply with is_related (true or false) and a single-sentence reason that
quotes the exact words that decided the classification.
"""

classifier_agent = Agent(
    chat_model,
    name="classifier",
    instructions=CLASSIFIER_INSTRUCTIONS,
    output_type=ClassificationResult,
    model_settings={"temperature": 0.0},
)

if __name__ == "__main__":
    samples = [
        # Mixed content -> expect False
        "Hi, I wanna know which medicines are soon to go out of stock and which is the latest marvel movie",
        # Fully related -> expect True
        "Add 20 packets of ORS - Electral from MedPlus with a 5% discount",
        # Off-topic -> expect False
        "What time does the grocery shop next door open?",
    ]
    for message in samples:
        response = classifier_agent.run_sync(message)
        print(f"{message!r}")
        print(
            f"  -> is_related={response.output.is_related}, reason={response.output.reason!r}\n"
        )
