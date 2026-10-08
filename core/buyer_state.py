"""What a sell-mode buyer is: its state, what it says each turn, and who it can be."""

import random
from dataclasses import dataclass, field

from .loader import load_sell_config


@dataclass
class BuyerState:
    """Represents the current state of the AI buyer in a sell-mode session."""

    readiness: float
    objections_raised: int = 0
    turn_count: int = 0
    has_committed: bool = False
    has_walked: bool = False
    persona: dict = field(default_factory=dict)
    difficulty: str = "medium"
    product_type: str = "default"

    def to_dict(self) -> dict:
        """Convert the state to a dictionary representation."""
        return {
            "readiness": round(self.readiness, 3),
            "objections_raised": self.objections_raised,
            "turn_count": self.turn_count,
            "has_committed": self.has_committed,
            "has_walked": self.has_walked,
            "difficulty": self.difficulty,
            "product_type": self.product_type,
            "persona_name": self.persona.get("name", "Unknown"),
        }

    @property
    def status(self) -> str:
        """Return the session status: 'sold', 'walked', or 'active'."""
        if self.has_committed:
            return "sold"
        if self.has_walked:
            return "walked"
        return "active"


@dataclass
class BuyerResponse:
    """Response from the AI buyer in a turn of the conversation."""

    content: str
    latency_ms: float
    provider: str
    model: str
    state_snapshot: dict
    coaching: dict | None = None


def personas_for(product_type: str) -> list[dict]:
    """The buyer personas available for a product (its own, else the general pool)."""
    personas = load_sell_config()["personas"]
    return personas.get(product_type) or personas["general"]


class UnknownPersona(ValueError):
    """The named persona is not in this product's pool."""

    def __init__(self, name: str, product_type: str):
        super().__init__(name, product_type)
        self.name, self.product_type = name, product_type


def select_persona(product_type: str, name: str | None = None) -> dict:
    """The named persona for this product, or a random one when no name is given.

    Raises UnknownPersona for a name that is not in this product's pool.
    """
    pool = personas_for(product_type)
    if not name:
        return random.choice(pool)
    for persona in pool:
        if persona["name"].lower() == name.strip().lower():
            return persona
    raise UnknownPersona(name, product_type)
