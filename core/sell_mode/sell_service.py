"""Sell-mode session setup, kept out of the route: the product picker and starting a session."""

from dataclasses import dataclass

from core.sell_mode.buyer_session import BuyerSession
from core.sell_mode.buyer_state import BuyerResponse, select_persona
from core.training.stage_jump import sell_history
from core.sell_mode.custom_buyer import parse_custom_buyer, parse_replay
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
    replay: list | None = None, knowledge: dict | None = None, jump: dict | None = None,
) -> SellStart:
    """Build the buyer, get its opening line and register the session.

    `difficulty` None means the configured default. `custom_buyer` (a buyer the learner described, e.g. from
    a real call) replaces the persona pick and brings its own objections; `replay` (a transcript ending with the
    buyer) is where the conversation starts instead of an opening line; `knowledge` the learner's own product details; `jump` ({stage, answers}) starts a practice call at a stage, on a
    short call so far built from the recap answers (training/stage_jump.py; ValueError for an unknown stage). Raises InvalidDifficulty,
    UnknownPersona or InvalidCustomBuyer for bad choices, and ProviderUnavailable when no LLM answers.
    `store` is the live-session store (needs `.set`).
    """
    persona, bank = parse_custom_buyer(custom_buyer) if custom_buyer is not None else (None, None)
    history = parse_replay(replay) if replay is not None else None
    session = BuyerSession(
        provider_type=provider,
        product_type=product_type,
        difficulty=_checked_difficulty(difficulty),
        persona=persona or select_persona(product_type, persona_name),
        objection=objection,
        objection_bank=bank,
        knowledge=knowledge,
    )
    if jump is not None and history is None:
        history = sell_history(session.persona, jump.get("stage"), jump.get("answers")) or None
        session.practice_from = jump.get("stage")
    opening = session.continue_from(history) if history else session.get_opening_message()
    store.set(session.session_id, session)
    return SellStart(session, opening)


def skills() -> dict:
    """The skills every sell session is scored on (buyer.yaml evaluation.criteria), for tracking them over time:
    id, label, the tip for when it is the weakest, its share of the overall score, the session that trains it (the
    default difficulty when it names none), the score that counts as strong (the default target), and the targets
    a learner can pick."""
    config = load_buyer_config()
    scoring, default_practice = config["evaluation"]["scoring"], {"difficulty": config["default_difficulty"]}
    return {
        "target": scoring["strong_score"],
        "targets": sorted(set(scoring["skill_targets"]) | {scoring["strong_score"]}),
        "skills": [
            {"id": name, "label": info["label"], "tip": info["tip"], "weight": info["weight"],
             "practice": info.get("practice", default_practice)}
            for name, info in config["evaluation"]["criteria"].items()
        ],
    }
