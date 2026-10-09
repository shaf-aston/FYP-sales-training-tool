"""Buy mode's coach: answers the learner's questions about the live call."""

import logging

from .constants import COACH_HISTORY_TURNS, LLM
from .loader import load_yaml
from .quiz import get_stage_rubric

logger = logging.getLogger(__name__)


def load_coach_config() -> dict:
    return load_yaml("coach.yaml")


COACH_STYLES = load_coach_config()["styles"]
DEFAULT_STYLE = load_coach_config()["default_style"]


def answer_question(router, call, question, style: str = DEFAULT_STYLE):
    """Answer the learner's question about the live call and sales technique."""
    cfg = load_coach_config()
    stage, strategy = call.current_stage, call.strategy
    rubric = get_stage_rubric(stage, strategy)

    speakers = cfg["speakers"]
    recent = "\n".join(
        f"{speakers.get(message.get('role'), '?')}: {message.get('content', '')}"
        for message in call.conversation_history[-COACH_HISTORY_TURNS:]
    )

    if style not in COACH_STYLES:
        logger.warning("Unknown coach style %r, defaulting to %s", style, DEFAULT_STYLE)
        style = DEFAULT_STYLE

    system_prompt = cfg["prompt"].format(
        strategy=strategy,
        stage=stage,
        goal=rubric["goal"],
        advance_when=rubric["advance_when"],
        concepts=", ".join(rubric["key_concepts"]),
        recent=recent,
        style=COACH_STYLES[style],
    )

    try:
        response = router.chat_with_fallback(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}],
            **LLM["coach_answer"],
        ).response
        answer = (
            response.content.strip()
            if response.content and not response.error
            else cfg["empty_answer"]
        )
        return {"answer": answer}
    except Exception as error:
        logger.warning(f"Coach answer fell back to a generic line: {error}")
        return {"answer": cfg["failed_answer"]}
