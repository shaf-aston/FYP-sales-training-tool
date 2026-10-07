"""Where one seller-mode call is: its history and the stage the script last showed."""

from typing import Any

from .enums import Stage

STRATEGY = "consultative"  # the only selling style; shown in the UI and used by the quiz


class CallFlow:
    """History plus the current stage; the script engine decides every move."""

    flow_type = STRATEGY

    def __init__(self) -> None:
        self.reset_to_initial()

    @property
    def user_turn_count(self) -> int:
        return sum(1 for m in self.conversation_history if m.get("role") == "user")

    def advance(self, target_stage: str) -> None:
        self.current_stage = Stage(target_stage)
        self.stage_turn_count = 0

    def add_turn(self, user_message: str, bot_response: str) -> None:
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": bot_response})
        self.stage_turn_count += 1

    def reset_to_initial(self) -> None:
        self.current_stage = Stage.INTENT
        self.stage_turn_count = 0
        self.conversation_history: list[dict[str, str]] = []

    def restore_state(self, state: dict[str, Any]) -> None:
        self.current_stage = Stage(state["current_stage"])
        self.stage_turn_count = state.get("stage_turn_count", 0)
