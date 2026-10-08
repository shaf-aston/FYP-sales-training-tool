"""Sell-mode session setup, kept out of the route: the product picker and starting a session."""

import secrets
from dataclasses import dataclass

from .buyer_session import BuyerSession
from .buyer_state import BuyerResponse, select_persona
from .loader import load_product_config, load_sell_config


class InvalidDifficulty(ValueError):
    """The requested difficulty has no profile in sell_config.yaml."""

    def __init__(self, choices: list[str]):
        super().__init__(choices)
        self.choices = choices


@dataclass(frozen=True)
class SellStart:
    session: BuyerSession
    opening: BuyerResponse


def product_groups() -> dict[str, list[dict]]:
    """Picker groups from sell_config.yaml; a product with no buyer personas is left out."""
    config = load_sell_config()
    products = load_product_config().get("products", {})
    return {
        strategy: [
            {
                "id": product_id,
                "label": products.get(product_id, {}).get("name")
                or product_id.replace("_", " ").title(),
            }
            for product_id in product_ids
            if config["personas"].get(product_id)
        ]
        for strategy, product_ids in config["product_groups"].items()
    }


def start_sell_session(
    store, *, difficulty: str, product_type: str, provider: str | None,
    persona_name: str | None, objection: str | None,
) -> SellStart:
    """Build the buyer, get its opening line, register and save the session.

    Raises InvalidDifficulty or UnknownPersona for bad choices, and ProviderUnavailable
    when no LLM answers. `store` is the live-session registry (needs `.set`).
    """
    choices = list(load_sell_config()["difficulty_profiles"])
    if difficulty not in choices:
        raise InvalidDifficulty(choices)
    persona = select_persona(product_type, persona_name)
    session = BuyerSession(
        provider_type=provider,
        product_type=product_type,
        difficulty=difficulty,
        persona=persona,
        session_id=secrets.token_hex(16),
        objection=objection,
    )
    opening = session.get_opening_message()
    store.set(session.session_id, session)
    session.save_session()
    return SellStart(session, opening)
