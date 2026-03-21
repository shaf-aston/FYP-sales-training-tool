"""Shared test mock classes — single source of truth."""


class MockLLMResponse:
    def __init__(self, content="Mock response", model="mock-model", latency_ms=50.0):
        self.content = content
        self.model = model
        self.latency_ms = latency_ms
        self.error = None


class MockProvider:
    def __init__(self, responses=None, model="mock-model"):
        self._responses = responses or []
        self._call_count = 0
        self._model = model

    def chat(self, messages, temperature=0.8, max_tokens=200, stage=None):
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = "Mock response"
        self._call_count += 1
        return MockLLMResponse(content=resp, model=self._model)

    def is_available(self):
        return True

    def get_model_name(self):
        return self._model


class MockFlowEngine:
    def __init__(self, stage="intent", strategy="consultative"):
        self.current_stage = stage
        self.flow_type = strategy
        self.conversation_history = []
        self.stage_turn_count = 0


class MockBot:
    def __init__(self, stage="intent", strategy="consultative"):
        self.flow_engine = MockFlowEngine(stage, strategy)
