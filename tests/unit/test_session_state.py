from app.contracts import SessionState


def test_session_state_is_explicitly_ephemeral():
    state = SessionState(authenticated=True, history=(("ถาม", "ตอบ"),))

    assert state.history == (("ถาม", "ตอบ"),)
    assert not hasattr(state, "database_key")
