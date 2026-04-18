"""Prompt integrity checks for stage coverage and dedup stability."""

from chatbot.flow import FLOWS, SalesFlowEngine
from chatbot.prompts import get_prompt
from chatbot.utils import Strategy


def _strategy_key(strategy) -> str:
    if isinstance(strategy, Strategy):
        return strategy.value
    return str(strategy)


def _required_prompt_keys(strategy) -> set[str]:
    stages = {
        stage.value if hasattr(stage, "value") else str(stage)
        for stage in FLOWS[strategy]["stages"]
    }
    if "intent" in stages:
        stages.add("intent_low")
    return stages


class TestPromptCoverage:
    def test_consultative_stage_prompts_exist(self):
        required = _required_prompt_keys(Strategy.CONSULTATIVE)
        missing = [
            key for key in sorted(required) if not get_prompt("consultative", key)
        ]
        assert not missing, f"Missing consultative prompts: {missing}"

    def test_transactional_stage_prompts_exist(self):
        required = _required_prompt_keys(Strategy.TRANSACTIONAL)
        missing = [
            key for key in sorted(required) if not get_prompt("transactional", key)
        ]
        assert not missing, f"Missing transactional prompts: {missing}"

    def test_intent_discovery_uses_consultative_prompt_set(self):
        engine = SalesFlowEngine("intent", "general product context")
        strategy_for_prompt = _strategy_key(engine._strategy_for_prompts)
        assert strategy_for_prompt == "consultative"
        assert get_prompt(strategy_for_prompt, "intent")


class TestPromptDedup:
    def test_objection_prompt_has_single_stage_exit_line(self):
        expected = "STAGE EXIT: Handled by the system on commitment or walkaway."
        for strategy in ("consultative", "transactional"):
            prompt = get_prompt(strategy, "objection")
            assert prompt.count(expected) == 1
