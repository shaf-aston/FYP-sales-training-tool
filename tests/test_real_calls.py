"""Real-call objections: only approved calls, buyer-voiced, no duplicates."""

from core.real_calls import extract_objections, pick_bank

TYPE_MAP = {"price": "price", "trust/legit": "skepticism"}
INDEX = [{"file": "a.txt", "included": "yes"}, {"file": "b.txt", "included": "no"}]


def _obj(text, file="a.txt", kind="price"):
    return {"file": file, "type": kind, "objection": text}


def test_extract_keeps_only_clean_buyer_lines():
    extracted = {"obj": [
        _obj("I can't afford it."),
        _obj("I can't afford it"),                        # exact duplicate, punctuation aside
        _obj("Too pricey.", file="b.txt"),                # call not approved
        _obj("Is this a scam?", kind="other"),            # type not mapped
        _obj("She only got approved for 1K on Klarna."),  # told about, not said by, a buyer
        _obj("Show me results (role-play prospect)", kind="trust/legit"),
    ]}
    pool = extract_objections(extracted, INDEX, TYPE_MAP)
    assert [(o["type"], o["text"]) for o in pool] == [
        ("price", "I can't afford it."),
        ("skepticism", "Show me results"),
    ]


def test_pick_bank_is_stable_per_session_and_capped():
    pool = [{"type": "price", "text": str(i)} for i in range(10)]
    assert pick_bank(pool, "s1", 3) == pick_bank(pool, "s1", 3)
    assert len(pick_bank(pool, "s1", 3)) == 3
    assert len(pick_bank(pool[:2], "s1", 5)) == 2
