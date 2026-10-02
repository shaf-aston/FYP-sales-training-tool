from backend import settings


def test_env_flag_parses_false_and_true(monkeypatch):
    monkeypatch.setenv("REQUIRE_ADMIN_FOR_STAGE_MUTATION", "false")
    assert settings.require_admin_for_stage_mutation({}) is False
    monkeypatch.setenv("REQUIRE_ADMIN_FOR_STAGE_MUTATION", "true")
    assert settings.require_admin_for_stage_mutation({}) is True
