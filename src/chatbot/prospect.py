"""Prospect mode: bot plays a buyer for sales practice roleplay training."""

import random
import time
from dataclasses import dataclass, field

from .loader import load_prospect_config, load_signals
from .providers.factory import create_provider
from .utils import clamp, range_label

SIGNALS = load_signals()

READINESSTHRESHOLDS = [0.2, 0.4, 0.6, 0.8]
READINESS_LABELS = [
    "Not buying it at all",
    "Still needs convincing",
    "On the fence — some interest but not sold",
    "Getting there, but a few things are holding them back",
    "Almost there — just needs one more good reason",
]


@dataclass
class ProspectState:
    """Represents the current state of a prospect in a sales roleplay session."""

    readiness: float
    objections_raised: int = 0
    turn_count: int = 0
    needs_disclosed: list = field(default_factory=list)
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
            "needs_disclosed": self.needs_disclosed,
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
class ProspectResponse:
    """Response from the prospect in a turn of the conversation."""

    content: str
    latency_ms: float
    provider: str
    model: str
    state_snapshot: dict
    coaching: dict | None = None


def select_persona(product_type: str, difficulty: str) -> dict:
    """Select a persona for the prospect based on product type and difficulty.

    Args:
        product_type: The type of product being sold.
        difficulty: The difficulty level (easy, medium, hard).

    Returns:
        A dictionary containing persona details (name, background, needs, etc.).
    """
    config = load_prospect_config()
    personas = config.get("personas", {})

    product_personas = personas.get(product_type)
    if product_personas:
        return random.choice(product_personas)

    general = personas.get("general", [])
    if general:
        return random.choice(general)

    # Fallback default persona
    return {
        "name": "Alex",
        "background": "Professional considering a purchase",
        "needs": ["value", "quality", "reliability"],
        "budget": "mid-range",
        "pain_points": ["current solution isn't meeting needs"],
        "personality": "Practical and straightforward",
    }


class ProspectSession:
    """Manages a prospect-mode conversation for sales roleplay training.

    The session simulates a buyer (prospect) with evolving readiness to purchase
    and tracks the salesperson's performance throughout the conversation.
    """

    def __init__(
        self,
        provider_type: str = "groq",
        product_type: str = "default",
        difficulty: str = "medium",
        persona: dict | None = None,
        session_id: str = "",
    ):
        """Initialize a prospect session.

        Args:
            provider_type: LLM provider to use (default: 'groq').
            product_type: Type of product being sold (default: 'default').
            difficulty: Session difficulty level (default: 'medium').
            persona: Optional persona dict; randomly selected if None.
            session_id: Optional session identifier.
        """
        self.session_id = session_id
        self.provider = create_provider(provider_type)
        self.provider_name = provider_type
        self.model_name = self.provider.get_model_name()

        config = load_prospect_config()
        profiles = config.get("difficulty_profiles", {})

        if difficulty not in profiles:
            difficulty = "medium"
        self.difficulty_profile = profiles[difficulty]
        behaviour = self.difficulty_profile["behaviour"]

        if persona is None:
            persona = select_persona(product_type, difficulty)
        self.persona = persona

        self.product_type = product_type
        self.product_context = self._load_product_context(product_type)

        self.state = ProspectState(
            readiness=behaviour["initial_readiness"],
            persona=persona,
            difficulty=difficulty,
            product_type=product_type,
        )

        self.conversation_history: list[dict] = []

        behaviour_rules = config.get("behaviour_rules", {})
        self.behaviour_rules = behaviour_rules.get(difficulty, "")

    def _load_product_context(self, product_type: str) -> str:
        """Load product context with prospect-specific knowledge.

        Args:
            product_type: The type of product being sold.

        Returns:
            Product context string for use in prompts.
        """
        try:
            from .knowledge import get_custom_knowledge_text
            from .loader import load_product_config

            products = load_product_config().get("products", {})
            product = products.get(product_type, products.get("default", {}))
            context = product.get("context", "various products and services")
            knowledge = product.get("knowledge", "")

            # Build prospect-specific context from persona data
            persona_context = self._build_persona_product_context()
            if persona_context:
                knowledge = (
                    f"{knowledge}\n\n{persona_context}"
                    if knowledge
                    else persona_context
                )

            # Keep mode-specific separation: only inject prospect custom KB
            prospect_knowledge = get_custom_knowledge_text()
            if prospect_knowledge:
                custom_block = (
                    f"--- BEGIN CUSTOM PROSPECT DATA ---\n{prospect_knowledge}\n--- END CUSTOM PROSPECT DATA ---\n"
                    "(You may know some of this as buyer research—do not assume full technical knowledge.)"
                )
                knowledge = (
                    f"{knowledge}\n\n{custom_block}" if knowledge else custom_block
                )

            return f"{context}\n\n{knowledge}" if knowledge else context
        except Exception:
            return "various products and services"

    def _build_persona_product_context(self) -> str:
        """Build product context from persona needs and pain points.

        Returns:
            Formatted persona context string.
        """
        parts = []
        needs = self.persona.get("needs", [])
        if needs:
            parts.append("BUYER'S KNOWN NEEDS: " + ", ".join(needs))
        pain_points = self.persona.get("pain_points", [])
        if pain_points:
            parts.append("BUYER'S PAIN POINTS: " + ", ".join(pain_points))
        budget = self.persona.get("budget")
        if budget:
            parts.append(f"BUYER'S BUDGET: {budget}")
        return "\n".join(parts)

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the prospect LLM.

        Returns:
            Formatted system prompt with current state and persona details.
        """
        config = load_prospect_config()
        template = config.get("system_prompt_template", "")

        behaviour = self.difficulty_profile["behaviour"]
        persona = self.persona

        readiness_desc = range_label(
            self.state.readiness, READINESSTHRESHOLDS, READINESS_LABELS
        )

        needs = persona.get("needs", [])
        pain_points = persona.get("pain_points", [])
        needs_formatted = "\n".join(f"  - {n}" for n in needs)
        pain_points_formatted = "\n".join(f"  - {p}" for p in pain_points)

        product_knowledge = ""
        if self.product_context:
            product_knowledge = f"PRODUCT INFORMATION (you may know some of this as a buyer doing research):\n{self.product_context}"

        prompt = template.format(
            name=persona.get("name", "Alex"),
            background=persona.get("background", ""),
            personality=persona.get("personality", ""),
            needs_formatted=needs_formatted,
            pain_points_formatted=pain_points_formatted,
            budget=persona.get("budget", "mid-range"),
            product_context=self.product_type.replace("_", " "),
            product_knowledge=product_knowledge,
            readiness_description=readiness_desc,
            objections_raised=self.state.objections_raised,
            max_objections=behaviour["max_objections"],
            turn_count=self.state.turn_count,
            behaviour_rules=self.behaviour_rules,
        )
        return prompt

    def get_opening_message(self) -> ProspectResponse:
        """Generate the prospect's opening message to start the conversation.

        Returns:
            ProspectResponse with the opening message and state snapshot.
        """
        system_prompt = self._build_system_prompt()
        persona_name = self.persona.get("name", "Alex")

        opening_instruction = (
            f"You are {persona_name}. Start the conversation naturally as a potential "
            f"customer. Introduce yourself briefly and say what brought you in today. "
            f"Keep it to 1-2 sentences. "
            f"Don't lay out everything you want straight away."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": opening_instruction},
        ]

        start = time.time()
        response = self.provider.chat(messages, temperature=0.7, max_tokens=150)
        latency = (time.time() - start) * 1000

        self.conversation_history.append(
            {
                "role": "assistant",
                "content": response.content,
            }
        )

        return ProspectResponse(
            content=response.content,
            latency_ms=round(latency, 1),
            provider=self.provider_name,
            model=self.model_name,
            state_snapshot=self.state.to_dict(),
        )

    def process_turn(
        self, user_message: str, show_hints: bool = False
    ) -> ProspectResponse:
        """Process a salesperson message and return the prospect's response.

        Args:
            user_message: The salesperson's message in this turn.
            show_hints: If True, generate an optional coaching hint for the user.

        Returns:
            ProspectResponse with prospect's reply, latency, and state snapshot.
        """
        self.state.turn_count += 1

        self.conversation_history.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        system_prompt = self._build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)

        start = time.time()
        response = self.provider.chat(messages, temperature=0.7, max_tokens=250)
        latency = (time.time() - start) * 1000

        self.conversation_history.append(
            {
                "role": "assistant",
                "content": response.content,
            }
        )

        # Update readiness based only on the salesperson's message
        self._update_readiness(user_message)

        end = self._check_end_conditions()
        if end == "sold":
            self.state.has_committed = True
        elif end == "walked":
            self.state.has_walked = True

        # Optional coaching hint
        coaching = None
        if show_hints and not self.state.has_committed and not self.state.has_walked:
            coaching = self._generate_coaching_hint(user_message)

        return ProspectResponse(
            content=response.content,
            latency_ms=round(latency, 1),
            provider=self.provider_name,
            model=self.model_name,
            state_snapshot=self.state.to_dict(),
            coaching=coaching,
        )

    def _update_readiness(self, user_msg: str) -> None:
        """Update prospect readiness score based on the salesperson's message.

        Args:
            user_msg: The salesperson's message to evaluate.
        """
        behaviour = self.difficulty_profile["behaviour"]

        # Deterministic scoring using only the user message
        rating = self._score_sales_message(user_msg)

        gain = behaviour["readiness_gain_per_good_turn"]
        loss = behaviour["readiness_loss_per_bad_turn"]

        if rating >= 4:
            readiness_change = gain * (rating - 3)  # 4→gain, 5→2*gain
        elif rating <= 2:
            readiness_change = -loss * (3 - rating)  # 2→-loss, 1→-2*loss
        else:
            readiness_change = 0.01  # Slight gain for neutral

        self.state.readiness = clamp(self.state.readiness + readiness_change)

    def _score_sales_message(self, user_msg: str) -> int:
        """Score a salesperson's message 1-5 using keyword signals.

        A higher score indicates stronger buying signals and better sales technique.

        Args:
            user_msg: The salesperson's message to score.

        Returns:
            Integer score from 1 (poor) to 5 (excellent).
        """
        from .analysis import classify_intent_level
        from .utils import contains_nonnegated_keyword

        msg_lower = user_msg.lower()
        msg_length = len(user_msg.split())

        # Base score starts at 3 (neutral)
        score = 3.0

        intent_level = classify_intent_level([], user_msg, signal_keywords=SIGNALS)

        # Dominant negative: walking signal wins — don't let positives cancel it
        if contains_nonnegated_keyword(msg_lower, SIGNALS.get("walking", [])):
            return 1

        # Strong positive signals (commitment, high intent)
        if contains_nonnegated_keyword(msg_lower, SIGNALS.get("commitment", [])):
            score += 2.0  # 5
        elif intent_level == "high":
            score += 1.0  # 4

        if intent_level == "low":
            score -= 0.5

        # Negative signals (objection, impatience)
        if contains_nonnegated_keyword(msg_lower, SIGNALS.get("objection", [])):
            score -= 0.5  # 2.5
        elif contains_nonnegated_keyword(msg_lower, SIGNALS.get("impatience", [])):
            score -= 1.0  # 2

        # Demand for directness (pressure without rapport)
        if contains_nonnegated_keyword(msg_lower, SIGNALS.get("demand_directness", [])):
            score -= 1.0  # 2

        # Message quality factors
        # Very short messages (< 5 words) are likely low-effort
        if msg_length < 5:
            score -= 0.5

        # Questions are good (discovery)
        if "?" in user_msg:
            score += 0.3

        # Early turns should focus on discovery, not pitching
        if self.state.turn_count <= 2:
            # Penalize price/feature mentions too early
            if any(
                word in msg_lower
                for word in ["price", "cost", "payment", "buy", "purchase"]
            ):
                score -= 0.5

        # Clamp to 1-5 range
        return max(1, min(5, round(score)))

    def _check_end_conditions(self) -> str | None:
        """Check if the session should end and determine the outcome.

        Returns:
            'sold' if prospect commits, 'walked' if prospect leaves, None otherwise.
        """
        behaviour = self.difficulty_profile["behaviour"]

        # Prospect commits
        if self.state.readiness >= 0.85 and self.state.turn_count >= 3:
            return "sold"

        # Prospect walks — out of patience
        if (
            self.state.turn_count >= behaviour["patience_turns"]
            and self.state.readiness < 0.4
        ):
            return "walked"

        # Prospect walks — readiness dropped to zero
        if self.state.readiness <= 0.0:
            return "walked"

        return None

    def _generate_coaching_hint(self, user_message: str) -> dict:
        """Generate a one-sentence coaching hint for the salesperson.

        Args:
            user_message: The salesperson's message to coach on.

        Returns:
            Dict with optional 'hint' key containing coaching feedback.
        """
        r = self.state.readiness
        behaviour = self.difficulty_profile["behaviour"]
        turns_left = behaviour["patience_turns"] - self.state.turn_count

        hint_prompt = f"""You are a sales coach observing a practice session.

The salesperson just said: "{user_message}"
The prospect's current readiness: {r:.2f} (0=hostile, 1=ready to buy)
Turns remaining before prospect leaves: {turns_left}
Difficulty: {self.state.difficulty}

Give one coaching tip — one sentence. Focus on what they should do next.
Don't give away what the prospect actually wants."""

        try:
            messages = [
                {"role": "system", "content": hint_prompt},
                {"role": "user", "content": "Give a coaching tip."},
            ]
            resp = self.provider.chat(messages, temperature=0.5, max_tokens=80)
            return {"hint": resp.content.strip()}
        except Exception:
            return {"hint": "Find out more before pitching anything."}

    def get_evaluation(self) -> dict:
        """Generate a final evaluation of the salesperson's performance.

        Returns:
            Dictionary containing scores, grades, feedback, and assessment.
        """
        from .prospect_evaluator import evaluate_prospect_session

        return evaluate_prospect_session(
            provider=self.provider,
            conversation_history=self.conversation_history,
            prospect_state=self.state,
            product_context=self.product_context,
        )
