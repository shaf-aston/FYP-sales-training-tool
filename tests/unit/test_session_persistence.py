import pytest

sp = pytest.importorskip("chatbot.session_persistence")

@pytest.fixture
def sessions_env(tmp_path, monkeypatch):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(sp, "SESSIONS_DIR", str(sessions_dir))
    return sp, sessions_dir

def test_save_load_session(sessions_env):
    sp_mod, sessions_dir = sessions_env
    sid = "test_session_123"
    
    # Save a session
    success = sp_mod.SessionPersistence.save(
        session_id=sid,
        product_type="productA",
        provider_type="providerB",
        flow_type="test_flow",
        current_stage="stage_2",
        stage_turn_count=3,
        conversation_history=[{"role": "user", "content": "hi"}],
        initial_flow_type="test_flow"
    )
    assert success is True
    
    # Verify file exists
    fpath = sessions_dir / f"{sid}.json"
    assert fpath.exists(), "session file not created"
    
    # Load session
    loaded = sp_mod.SessionPersistence.load(sid)
    assert loaded is not None
    assert loaded["session_id"] == sid
    assert loaded["product_type"] == "productA"
    assert loaded["stage_turn_count"] == 3
    assert loaded["conversation_history"][0]["content"] == "hi"

def test_atomic_write_ignores_partial_tmp_files(sessions_env):
    sp_mod, sessions_dir = sessions_env
    sid = "partial_test"
    # Simulate an interrupted write: create a .tmp partial file directly in the sessions dir
    tmp_path = sessions_dir / f"{sid}.json.tmp"
    tmp_path.write_text('{"session_id": "partial_test", "turns": [')
    
    # Expect load to return None because the actual .json doesn't exist yet
    loaded = sp_mod.SessionPersistence.load(sid)
    assert loaded is None
