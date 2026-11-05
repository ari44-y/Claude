"""テストの共通の準備（pytest の fixture）。

fixture：テスト関数の引数に名前を書くだけで、準備したものを渡してくれる仕組み。
例：def test_xxx(client, clock): ... と書くと、下の client() と clock() の戻り値が渡される。
"""

import os

# app を import する前に設定する（app.config の settings は import した時点で値が決まるため）
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SCHEDULER_ENABLED"] = "false"

from datetime import datetime  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.config import TZ  # noqa: E402
from app.db import Base, get_db, get_now, make_engine  # noqa: E402
from app.main import app  # noqa: E402


class Clock:
    """テスト用の時計。clock.set(2026, 11, 23, 7, 0) で「日本時間のその時刻」にできる。"""

    def __init__(self):
        self.now = datetime(2026, 11, 5, 12, 0, tzinfo=TZ)

    def set(self, *args) -> datetime:
        self.now = datetime(*args, tzinfo=TZ)
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def session(tmp_path):
    """テストごとに空の DB を作る。tmp_path は pytest が用意する一時フォルダ。"""
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    # テストでは Alembic を使わず、models.py の定義からテーブルを直接作る（速いため）
    Base.metadata.create_all(engine)
    SessionTest = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionTest() as s:
        yield s  # yield の後ろは、テストが終わったあとの片付け
    engine.dispose()


@pytest.fixture
def client(session: Session, clock: Clock):
    """API を呼ぶためのクライアント。DB と時計をテスト用に差し替える。"""
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_now] = lambda: clock.now
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
