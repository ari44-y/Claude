"""React のビルド結果（frontend/dist）を FastAPI から配信する。

本番では FastAPI 1つで「API」と「画面」の両方を出す（要件定義書 6章）。
開発中は Vite の開発サーバーが画面を出すので、これは使われない。
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """dist の中身を配信する。dist がなければ何もしない（ビルド前でも API は動くように）。

    必ず API のルーターを登録した「後」に呼ぶこと。
    下の /{path:path} はどんな URL にも当てはまるので、先に登録すると API より優先されてしまう。
    """
    if not (dist / "index.html").is_file():
        return

    dist = dist.resolve()
    index = dist / "index.html"

    # /assets/index-DuEk6gxb.js のようなファイル。名前に中身のハッシュが入っているので、
    # 中身が変わると名前も変わる → ブラウザが古いファイルを使い続ける心配がない
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        # 存在しない API は、画面ではなく 404 を返す
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "見つかりません")

        # favicon.svg など、dist の直下のファイル
        file = (dist / path).resolve()
        # is_relative_to：「../../etc/passwd」のように dist の外を指す URL を拒否する
        if path and file.is_relative_to(dist) and file.is_file():
            return FileResponse(file)

        # それ以外（/tasks など）は全部 index.html を返す。
        # どの画面を出すかは、ブラウザ側の React Router が URL を見て決める（SPA の仕組み）。
        # no-cache：index.html だけは毎回サーバーに確認させ、更新がすぐ反映されるようにする
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
