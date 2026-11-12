"""The written critique under an SOP's checklist and under a call checked against it: rules pick what it says."""

from core.infra.loader import CONFIG_DIR, load_yaml
from core.sop.adherence import Adherence, StepResult
from core.sop.checklist import ElementResult
from core.sop.critique import call_critique, sop_critique

CFG = load_yaml("sop.yaml")


def element(eid, covered):
    e = next(x for x in CFG["elements"] if x["id"] == eid)
    return ElementResult(eid, e["label"], covered, "a step" if covered else None, e["why"])


def test_a_complete_sop_is_told_to_check_a_call_next():
    text = sop_critique([element(e["id"], True) for e in CFG["elements"]], CFG)
    assert text == CFG["critique"]["sop"]["complete"]


def test_the_costliest_gap_is_named_first_with_why_it_matters():
    elements = [element(e["id"], e["id"] not in ("opening", "close", "urgency")) for e in CFG["elements"]]
    text = sop_critique(elements, CFG)
    assert text.startswith(f"Your SOP covers {len(elements) - 3} of {len(elements)} parts of a good call. "
                           "The biggest gap is the close: Asking clearly")
    assert "It also has nothing for why now and opening and agenda." in text


def step(done, conditional=False, n=1):
    return StepResult("Discover", f"Ask question {n}", done, conditional, n if done else None, "said" if done else None)


def test_a_call_names_the_first_skipped_step_and_how_many_more():
    result = Adherence([step(True, n=1), step(False, n=2), step(False, n=3), step(True, n=4)], 50, True)
    assert call_critique(result, CFG) == ('The rep carried out only 2 of 4 steps (50%). The first step they skipped was '
                                          '"Ask question 2" (Discover). 1 other step went unsaid too. The steps they did '
                                          "came in the SOP's order.")


def test_a_conditional_step_never_needed_does_not_count_against_the_call():
    result = Adherence([step(True, n=1), step(False, conditional=True, n=2)], 100, True)
    assert call_critique(result, CFG) == "The rep carried out 1 of 1 steps (100%)."


def test_the_routes_return_the_critique(client):
    read = client.post("/api/sop/read", json={"text": (CONFIG_DIR / "sop_sample.md").read_text()}).get_json()
    assert read["critique"].startswith("Your SOP covers")
    call = (CONFIG_DIR / "calls_sample.txt").read_text()
    checked = client.post("/api/sop/check", json={"stages": read["stages"], "call": {"text": call}}).get_json()
    assert checked["critique"].startswith("The rep carried out")
