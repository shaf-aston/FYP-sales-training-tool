"""Sell-mode session setup, kept out of the route: the product picker and starting a session."""

from dataclasses import dataclass

from core.sell_mode.buyer_session import BuyerSession
from core.sell_mode.buyer_state import BuyerResponse, select_persona
from core.sell_mode.custom_buyer import parse_custom_buyer
from core.sell_mode.session_review import build_review
from core.infra.loader import load_buyer_config, load_buyer_products


class InvalidDifficulty(ValueError):
    """The requested difficulty has no profile in buyer.yaml."""

    def __init__(self, choices: list[str]):
        super().__init__(choices)
        self.choices = choices


@dataclass(frozen=True)
class SellStart:
    session: BuyerSession
    opening: BuyerResponse


def product_groups() -> dict[str, list[dict]]:
    """Picker groups from buyer.yaml; a product with no buyer personas is left out."""
    config = load_buyer_config()
    products = load_buyer_products()["products"]
    return {
        group: [
            {
                "id": product_id,
                "label": products.get(product_id, {}).get("name")
                or product_id.replace("_", " ").title(),
            }
            for product_id in product_ids
            if config["personas"].get(product_id)
        ]
        for group, product_ids in config["product_groups"].items()
    }


def _checked_difficulty(difficulty: str | None) -> str:
    """The difficulty asked for, or the configured default for None. Raises InvalidDifficulty."""
    config = load_buyer_config()
    if difficulty is None:
        return config["default_difficulty"]
    choices = list(config["difficulty_profiles"])
    if difficulty not in choices:
        raise InvalidDifficulty(choices)
    return difficulty


def review_transcript(history: list[dict], difficulty: str | None) -> dict:
    """The turn-by-turn review of any transcript (e.g. a real call), replayed at a difficulty's behaviour:
    the same review a practice session gets. Raises InvalidDifficulty."""
    behaviour = load_buyer_config()["difficulty_profiles"][_checked_difficulty(difficulty)]["behaviour"]
    review = build_review(history, behaviour)
    review.pop("readiness_exact")   # for rewinding a live session only
    return review


def start_sell_session(
    store, *, difficulty: str | None, product_type: str, provider: str | None,
    persona_name: str | None, objection: str | None, custom_buyer: dict | None = None,
) -> SellStart:
    """Build the buyer, get its opening line and register the session.

    `difficulty` None means the configured default. `custom_buyer` (a buyer the learner described, e.g. from
    a real call) replaces the persona pick and brings its own objections. Raises InvalidDifficulty,
    UnknownPersona or InvalidCustomBuyer for bad choices, and ProviderUnavailable when no LLM answers.
    `store` is the live-session store (needs `.set`).
    """
    persona, bank = parse_custom_buyer(custom_buyer) if custom_buyer is not None else (None, None)
    session = BuyerSession(
        provider_type=provider,
        product_type=product_type,
        difficulty=_checked_difficulty(difficulty),
        persona=persona or select_persona(product_type, persona_name),
        objection=objection,
        objection_bank=bank,
    )
    opening = session.get_opening_message()
    store.set(session.session_id, session)
    return SellStart(session, opening)
