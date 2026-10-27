"""Where one buy-mode call is: its history and the stage the script last showed."""

from typing import Any

from core.buy_mode.stage import Stage


class CallFlow:
    """History plus the current stage; the script engine decides every move."""

    def __init__(self) -> None:
        self.reset_to_initial()

    @property
    def user_turn_count(self) -> int:
        return sum(1 for m in self.conversation_history if m.get("role") == "user")

    def advance(self, target_stage: str) -> None:
        self.current_stage = Stage(target_stage)
        self.stage_turn_count = 0

    def add_turn(self, user_message: str, seller_reply: str) -> None:
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": seller_reply})
        self.stage_turn_count += 1

    def reset_to_initial(self) -> None:
        self.current_stage = Stage.INTENT
        self.stage_turn_count = 0
        self.conversation_history: list[dict[str, str]] = []

    def restore_state(self, state: dict[str, Any]) -> None:
        self.current_stage = Stage(state["current_stage"])
        self.stage_turn_count = state.get("stage_turn_count", 0)
