from core.analysis import extract_user_keywords


def test_extract_user_keywords_prefers_recent_user_terms():
    history = [
        {"role": "user", "content": "I need affordable solar panels for my house"},
        {"role": "assistant", "content": "Tell me more."},
        {"role": "user", "content": "Battery backup and installer support matter most"},
    ]

    assert extract_user_keywords(history, max_keywords=4) == [
        "installer",
        "support",
        "matter",
        "most",
    ]
