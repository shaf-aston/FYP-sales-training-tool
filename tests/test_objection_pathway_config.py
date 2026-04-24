from backend.security import SessionSecurityManager
from core.objection import analyse_objection_pathway, validate_pathway_config


def test_pathway_config_validates_cleanly():
    is_valid, errors = validate_pathway_config()

    assert is_valid is True
    assert errors == []


def test_money_objection_maps_to_resource_pathway():
    pathway = analyse_objection_pathway("It is too expensive for me right now.")

    assert pathway["type"] == "money"
    assert pathway["category"] == "resource"
    assert pathway["entry_question"]
    assert pathway["open_wallet_applicable"] is True
    assert pathway["reframes"] == [
        "change_of_process",
        "island_mountain",
        "identity_loop",
    ]
    assert "change_of_process" in pathway["reframe_descriptions"]


def test_background_cleanup_is_idempotent(monkeypatch):
    started = []

    class DummyThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            started.append((self.target, self.daemon))

    monkeypatch.setattr("backend.security.threading.Thread", DummyThread)

    manager = SessionSecurityManager(manager_name="test sessions")
    manager.start_background_cleanup()
    manager.start_background_cleanup()

    assert len(started) == 1
