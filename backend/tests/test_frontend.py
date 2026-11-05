"""画面ファイルの配信のテスト。

本物の frontend/dist ではなく、一時フォルダに小さな dist を作って確かめる。
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.frontend import mount_frontend


def _client(tmp_path) -> TestClient:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id=root></div>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (dist / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("見えてはいけない")

    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    mount_frontend(app, dist)
    return TestClient(app)


def test_spa_routes_return_index(tmp_path):
    c = _client(tmp_path)
    for url in ["/", "/tasks", "/tasks?date=2026-11-07"]:
        res = c.get(url)
        assert res.status_code == 200
        assert "root" in res.text
        assert res.headers["cache-control"] == "no-cache"


def test_static_files(tmp_path):
    c = _client(tmp_path)
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/favicon.svg").text == "<svg/>"


def test_api_still_works_and_unknown_api_is_404(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/health").json() == {"status": "ok"}
    assert c.get("/api/unknown").status_code == 404


def test_cannot_read_outside_dist(tmp_path):
    c = _client(tmp_path)
    res = c.get("/..%2Fsecret.txt")
    assert "見えてはいけない" not in res.text


def test_no_dist_does_nothing(tmp_path):
    app = FastAPI()
    mount_frontend(app, tmp_path / "nothing")
    assert TestClient(app).get("/").status_code == 404
