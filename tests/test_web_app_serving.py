"""The built Next.js app (web/out) is served at the site root; /api stays JSON."""
from pathlib import Path

import pytest

from backend.app import app

OUT = Path(__file__).resolve().parent.parent / "web" / "out"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_build_is_committed():
    # The server deploy has no Node, so the built app must be in the repo.
    assert (OUT / "index.html").is_file(), "run `npm run build` in web/ and commit web/out"
    assert (OUT / "knowledge" / "index.html").is_file()


def test_root_serves_the_app(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Eloquence" in response.get_data(as_text=True)


def test_folder_paths_serve_their_index(client):
    assert client.get("/knowledge/").status_code == 200


def test_unknown_page_is_404(client):
    assert client.get("/no-such-page/").status_code == 404


def test_unknown_api_route_is_not_the_app(client):
    response = client.get("/api/no-such-route")
    assert response.status_code == 404
    assert "Eloquence" not in response.get_data(as_text=True)


def test_path_traversal_is_refused(client):
    assert client.get("/../backend/app.py").status_code == 404
    assert client.get("/%2e%2e/backend/app.py").status_code == 404
