"""/api/account and /api/team through the app: the login cookie, access rules and privacy."""
import pytest

from core.infra.loader import CONFIG_DIR


@pytest.fixture
def app_client():
    from backend.app import app

    app.config["TESTING"] = True
    return app.test_client


def signup(client, email="ann@x.co", name="Ann", password="longenough"):
    return client.post("/api/account/signup", json={"email": email, "name": name, "password": password})


def test_me_is_empty_until_signup_logs_you_in(app_client):
    c = app_client()
    assert c.get("/api/account/me").get_json() == {"success": True, "user": None, "team": None}
    made = signup(c)
    assert made.status_code == 201
    cookie = made.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert c.get("/api/account/me").get_json()["user"]["email"] == "ann@x.co"


def test_logout_then_login(app_client):
    c = app_client()
    signup(c)
    c.post("/api/account/logout")
    assert c.get("/api/account/me").get_json()["user"] is None
    assert c.post("/api/account/login", json={"email": "ann@x.co", "password": "nope-nope"}).status_code == 401
    assert c.post("/api/account/login", json={"email": "ANN@x.co", "password": "longenough"}).status_code == 200
    assert c.get("/api/account/me").get_json()["user"]["name"] == "Ann"


def test_signup_errors_name_the_field(app_client):
    body = signup(app_client(), password="short").get_json()
    assert body["field"] == "password" and "8 characters" in body["error"]


@pytest.mark.parametrize("method, path", [
    ("get", "/api/account/skills"), ("post", "/api/account/skills"), ("get", "/api/account/prospects"),
    ("post", "/api/account/prospects"), ("delete", "/api/account/prospects/1"), ("get", "/api/account/export"),
    ("post", "/api/account/delete"), ("get", "/api/team"), ("post", "/api/team/create"), ("post", "/api/team/join"),
])
def test_everything_kept_needs_a_login(app_client, method, path):
    response = getattr(app_client(), method)(path, json={})
    assert response.status_code == 401 and response.get_json()["code"] == "LOGIN_REQUIRED"


def test_skill_history_syncs_up_and_comes_back(app_client):
    c = app_client()
    signup(c)
    entries = [{"sessionId": "s1", "at": 1000, "overall": 61, "scores": {"needs_discovery": 55, "rapport_building": 70}}]
    assert c.post("/api/account/skills", json={"entries": entries}).get_json()["stored"] == 1
    assert c.get("/api/account/skills").get_json()["entries"] == entries
    assert c.post("/api/account/skills", json={"entries": "nope"}).status_code == 400


def test_save_a_prospect_from_a_call_and_practise_list(app_client):
    c = app_client()
    signup(c)
    profile = c.post("/api/calls/read", json={"text": (CONFIG_DIR / "calls_sample.txt").read_text("utf-8")}).get_json()["profile"]
    custom = {k: profile[k] for k in ("name", "background", "personality", "budget", "needs", "pain_points", "objections")}
    saved = c.post("/api/account/prospects", json={"profile": custom})
    assert saved.status_code == 201
    listed = c.get("/api/account/prospects").get_json()["prospects"]
    assert [p["name"] for p in listed] == ["Dan"] and listed[0]["profile"]["objections"] == profile["objections"]
    assert "custom" not in listed[0]["profile"]
    assert c.post("/api/account/prospects", json={"profile": {"background": "no name"}}).status_code == 400
    assert c.delete(f"/api/account/prospects/{listed[0]['id']}").status_code == 200
    assert c.delete(f"/api/account/prospects/{listed[0]['id']}").status_code == 404


def test_delete_account_needs_the_password_and_removes_everything(app_client):
    c = app_client()
    signup(c)
    assert c.post("/api/account/delete", json={"password": "wrong-one"}).status_code == 403
    assert c.post("/api/account/delete", json={"password": "longenough"}).status_code == 200
    assert c.get("/api/account/me").get_json()["user"] is None
    assert c.post("/api/account/login", json={"email": "ann@x.co", "password": "longenough"}).status_code == 401


def test_export_holds_everything_kept(app_client):
    c = app_client()
    signup(c)
    body = c.get("/api/account/export").get_json()
    assert set(body) >= {"user", "team", "skills", "prospects"}


def test_managers_see_the_team_and_its_code_reps_do_not(app_client):
    boss, rep = app_client(), app_client()
    signup(boss, "boss@x.co", "Boss")
    signup(rep, "rep@x.co", "Rep")
    code = boss.post("/api/team/create", json={"name": "Closers"}).get_json()["team"]["invite_code"]
    assert rep.post("/api/team/join", json={"code": "nope"}).get_json()["code"] == "UNKNOWN_CODE"
    assert rep.post("/api/team/join", json={"code": code}).status_code == 200
    as_boss, as_rep = boss.get("/api/team").get_json(), rep.get("/api/team").get_json()
    assert {m["name"] for m in as_boss["members"]} == {"Boss", "Rep"} and as_boss["team"]["invite_code"] == code
    assert [m["name"] for m in as_rep["members"]] == ["Boss"] and as_rep["team"]["invite_code"] is None
    assert "email" not in as_rep["members"][0]
