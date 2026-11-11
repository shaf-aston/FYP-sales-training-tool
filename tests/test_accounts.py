"""core/accounts: users, passwords, teams and the learner's library, on a fresh database per test."""
import pytest

from core.accounts.db import MIGRATIONS, database
from core.accounts.library import Library, LibraryError
from core.accounts.passwords import check_password, hash_password
from core.accounts.teams import MANAGER, REP, TeamError, Teams
from core.accounts.users import AccountError, Users


@pytest.fixture
def db():
    return database()


def entry(session_id="s1", at=100, overall=60, **scores):
    return {"sessionId": session_id, "at": at, "overall": overall, "scores": scores or {"needs_discovery": 60}}


def test_the_schema_is_at_the_latest_migration_and_rerunning_is_a_no_op(db):
    assert db.migrate() == len(MIGRATIONS) == db.migrate()


def test_passwords_hash_with_a_salt_and_check_in_constant_form():
    first, second = hash_password("correct horse"), hash_password("correct horse")
    assert first != second and first.startswith("scrypt$")
    assert check_password("correct horse", first) and not check_password("wrong", first)
    assert not check_password("x", "garbage") and not check_password("x", "md5$1$2$3$aa$bb")


def test_sign_up_then_log_in_with_any_case_email(db):
    users = Users(db)
    made = users.create(" Ann@Example.com ", "  Ann   Lee ", "longenough")
    assert (made.email, made.name) == ("Ann@Example.com", "Ann Lee")
    assert users.authenticate("ann@example.com", "longenough") == made
    assert users.authenticate("ann@example.com", "wrong-pass") is None
    assert users.authenticate("nobody@example.com", "longenough") is None


@pytest.mark.parametrize("email, name, password, field, code", [
    ("not-an-email", "Ann", "longenough", "email", "invalid"),
    ("a@b.co", " ", "longenough", "name", "invalid"),
    ("a@b.co", "Ann", "short", "password", "too_short"),
])
def test_sign_up_names_the_field_to_fix(db, email, name, password, field, code):
    with pytest.raises(AccountError) as caught:
        Users(db).create(email, name, password)
    assert (caught.value.field, caught.value.code) == (field, code)


def test_one_account_per_email(db):
    Users(db).create("a@b.co", "Ann", "longenough")
    with pytest.raises(AccountError) as caught:
        Users(db).create("A@B.CO", "Other", "longenough")
    assert caught.value.code == "taken"


def test_teams_have_one_manager_and_reps_join_by_code(db):
    users, teams = Users(db), Teams(db)
    boss, rep = users.create("boss@x.co", "Boss", "longenough"), users.create("rep@x.co", "Rep", "longenough")
    made = teams.create(boss.id, "Closers")
    assert made.role == MANAGER and len(made.invite_code) == 8
    joined = teams.join(rep.id, made.invite_code.lower())
    assert joined.role == REP and joined.team_id == made.team_id
    assert [(m.name, m.role) for m in teams.members(made.team_id)] == [("Boss", MANAGER), ("Rep", REP)]
    with pytest.raises(TeamError):
        teams.join(rep.id, made.invite_code)
    with pytest.raises(TeamError):
        teams.join(users.create("c@x.co", "C", "longenough").id, "WRONGCOD")


def test_a_team_always_keeps_a_manager(db):
    users, teams = Users(db), Teams(db)
    boss, rep = users.create("boss@x.co", "Boss", "longenough"), users.create("rep@x.co", "Rep", "longenough")
    code = teams.create(boss.id, "Closers").invite_code
    teams.join(rep.id, code)
    users.delete(boss.id)                       # deleting the manager's account...
    assert teams.membership(rep.id).role == MANAGER   # ...makes the longest-standing rep the manager
    teams.leave(rep.id)                          # the last member leaving deletes the team
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0


def test_deleting_an_account_deletes_everything_kept_for_it(db):
    users, library = Users(db), Library(db)
    ann = users.create("a@b.co", "Ann", "longenough")
    library.add_skill_entries(ann.id, [entry()])
    library.save_prospect(ann.id, {"name": "Dan"})
    users.delete(ann.id)
    with db.connect() as conn:
        counts = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("users", "skill_entries", "prospects")]
    assert counts == [0, 0, 0]


def test_skill_history_replaces_a_rescored_session_and_keeps_the_newest(db, monkeypatch):
    monkeypatch.setattr("core.accounts.library.MAX_SKILL_ENTRIES", 2)
    ann = Users(db).create("a@b.co", "Ann", "longenough")
    library = Library(db)
    library.add_skill_entries(ann.id, [entry("s1", 100), entry("s2", 200), entry("s1", 300, 70)])
    library.add_skill_entries(ann.id, [entry("s3", 400)])
    assert [(e["sessionId"], e["at"]) for e in library.skill_entries(ann.id)] == [("s1", 300), ("s3", 400)]


@pytest.mark.parametrize("bad", [
    {"sessionId": "s1", "at": 1, "overall": 60, "scores": {}},
    {"sessionId": "s1", "at": 1, "overall": 160, "scores": {"a": 1}},
    {"sessionId": "s1", "at": "now", "overall": 60, "scores": {"a": 1}},
    {"sessionId": "s1", "at": 1, "overall": True, "scores": {"a": 1}},
    "s1",
])
def test_a_malformed_skill_entry_stores_nothing(db, bad):
    ann = Users(db).create("a@b.co", "Ann", "longenough")
    with pytest.raises(LibraryError):
        Library(db).add_skill_entries(ann.id, [entry("ok"), bad])
    assert Library(db).skill_entries(ann.id) == []


def test_prospects_are_private_and_capped(db, monkeypatch):
    monkeypatch.setattr("core.accounts.library.MAX_SAVED_PROSPECTS", 1)
    users, library = Users(db), Library(db)
    ann, bob = users.create("a@b.co", "Ann", "longenough"), users.create("b@b.co", "Bob", "longenough")
    saved = library.save_prospect(ann.id, {"name": "Dan"})
    with pytest.raises(LibraryError):
        library.save_prospect(ann.id, {"name": "Eve"})
    assert library.prospects(bob.id) == []
    assert not library.delete_prospect(bob.id, saved["id"])   # someone else's prospect
    assert library.delete_prospect(ann.id, saved["id"])
