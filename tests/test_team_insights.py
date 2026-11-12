"""Manager insights: levels and guidelines from members' skill history (core/training/team_insights.py, /api/team)."""
import pytest

from core.infra.loader import load_yaml
from core.training.team_insights import build_insights

CFG = load_yaml("insights.yaml")
SKILLS = [{"id": "needs", "label": "needs discovery", "tip": "Ask one open question."},
          {"id": "objections", "label": "objection handling", "tip": "Acknowledge, then reframe."}]
DAY = 86_400_000
NOW = 1_800_000_000_000


def entries(*pairs, last=NOW):
    """Sessions one day apart ending at `last`, each (needs, objections) score (None = not measured)."""
    out = []
    for i, (n, o) in enumerate(pairs):
        scores = {k: v for k, v in (("needs", n), ("objections", o)) if v is not None}
        out.append({"sessionId": f"s{i}", "at": last - (len(pairs) - 1 - i) * DAY, "overall": 60, "scores": scores})
    return out


def test_levels_are_recent_averages_and_the_weakest_is_furthest_below_target():
    data = build_insights([(1, "Ann", entries((80, 40), (82, 50), (84, 60)))], SKILLS, 70, NOW, CFG)
    ann = data["members"][0]
    assert ann["levels"] == {"needs": 82, "objections": 50} and ann["weakest"] == "objections"
    assert data["team"] == {"needs": 82, "objections": 50}


def test_a_team_wide_gap_becomes_a_group_guideline_with_its_numbers():
    team = [(1, "Ann", entries((80, 40), (80, 50))), (2, "Bo", entries((75, 55), (75, 60))), (3, "Cy", entries((90, 90), (90, 90)))]
    lines = build_insights(team, SKILLS, 70, NOW, CFG)["guidelines"]
    assert lines[0].startswith("Most of the team is below target on objection handling: 2 of 3 members")
    assert "Acknowledge, then reframe." in lines[0]


def test_members_who_are_new_or_idle_are_named_not_ranked():
    team = [(1, "Ann", entries((50, 50))), (2, "Bo", entries((80, 80), (80, 80), last=NOW - 10 * DAY)), (3, "Cy", [])]
    data = build_insights(team, SKILLS, 70, NOW, CFG)
    assert [m["judged"] for m in data["members"]] == [False, True, False]
    assert any(g.startswith("2 members have not practised in 7 days: Bo, Cy") for g in data["guidelines"])
    assert any(g.startswith("2 members have fewer than 2 scored sessions") for g in data["guidelines"])


def test_improvement_is_recognised():
    rising = entries(*[(50, None)] * 5, *[(70, None)] * 5)
    lines = build_insights([(1, "Ann", rising)], SKILLS, 60, NOW, CFG)["guidelines"]
    assert any("Ann improved needs discovery by 20 points" in g for g in lines)


def test_everyone_at_target_says_raise_it():
    lines = build_insights([(1, "Ann", entries((90, 90), (90, 90)))], SKILLS, 70, NOW, CFG)["guidelines"]
    assert lines == [CFG["guidelines"]["all_met"]]


# --- routes ---

@pytest.fixture
def app_client():
    from backend.app import app

    app.config["TESTING"] = True
    return app.test_client


def signup(c, email, name):
    c.post("/api/account/signup", json={"email": email, "name": name, "password": "longenough"})


def test_only_managers_get_insights_and_the_csv(app_client):
    boss, rep = app_client(), app_client()
    signup(boss, "boss@x.co", "Boss")
    signup(rep, "rep@x.co", "Rep")
    code = boss.post("/api/team/create", json={"name": "Closers"}).get_json()["team"]["invite_code"]
    rep.post("/api/team/join", json={"code": code})
    rep.post("/api/account/skills", json={"entries": [
        {"sessionId": f"s{i}", "at": 1_700_000_000_000 + i, "overall": 60, "scores": {"objection_handling": 40 + i}} for i in range(3)]})
    assert rep.get("/api/team/insights").get_json()["code"] == "NOT_MANAGER"
    body = boss.get("/api/team/insights?target=80").get_json()
    assert body["target"] == 80 and [m["name"] for m in body["members"]] == ["Rep"]   # a manager with no sessions
    assert body["members"][0]["levels"]["objection_handling"] == 41
    assert boss.get("/api/team/insights?target=13").get_json()["target"] == 70   # not offered: the default
    csv_text = boss.get("/api/team/insights.csv").get_data(as_text=True)
    assert csv_text.splitlines()[0].startswith("Member,Scored sessions,Last practised,")
    assert "Rep,3," in csv_text


def test_a_tie_on_how_many_are_below_goes_to_the_lowest_skill():
    team = [(1, "Ann", entries((65, 50), (65, 50))), (2, "Bo", entries((66, 55), (66, 55)))]
    lines = build_insights(team, SKILLS, 70, NOW, CFG)["guidelines"]
    assert lines[0].startswith("Most of the team is below target on objection handling")


def test_a_name_that_looks_like_a_formula_is_text_in_the_csv(app_client):
    boss, rep = app_client(), app_client()
    signup(boss, "boss2@x.co", "Boss")
    signup(rep, "rep2@x.co", '=HYPERLINK("http://evil.example","Open")')
    code = boss.post("/api/team/create", json={"name": "Closers"}).get_json()["team"]["invite_code"]
    rep.post("/api/team/join", json={"code": code})
    rows = boss.get("/api/team/insights.csv").get_data(as_text=True).splitlines()
    assert rows[1].startswith("\"'=HYPERLINK(")
