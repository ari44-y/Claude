"""DB の接続と、テーブル定義で共通に使う部品。"""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import settings


class Base(DeclarativeBase):
    """すべてのテーブル（models.py のクラス）の親クラス。

    Alembic はこの Base.metadata を見て、テーブルの差分を見つける。
    """


class UTCDateTime(TypeDecorator):
    """日時を「UTC・タイムゾーンなし」で保存し、読み出すときに UTC を付け直す型。

    SQLite にはタイムゾーン付きの日時型がない。そのまま保存すると
    「この 8:00 は日本時間？UTC？」が分からなくなるので、
    保存するときは必ず UTC に揃え、読み出したら UTC の印を付けて返す。
    """

    impl = DateTime
    cache_ok = True  # SQLAlchemy に「この型は SQL のキャッシュに使っても安全」と伝える

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        # Python → DB の方向
        if value is None:
            return None
        if value.tzinfo is None:
            # タイムゾーンなしの日時は、どこの時刻か分からないので受け付けない
            raise ValueError("タイムゾーン付きの日時を渡してください")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        # DB → Python の方向
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def make_engine(url: str) -> Engine:
    """DB への接続口（Engine）を作る。テストでは別の URL で呼ぶ。"""
    if url.startswith("sqlite:///") and ":memory:" not in url:
        # DB ファイルを置くフォルダがなければ作る
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        url,
        # FastAPI は同期の API をスレッドで動かすので、
        # 「作ったスレッド以外から使うな」という SQLite の確認を外す
        connect_args={"check_same_thread": False},
    )

    # 接続するたびに SQLite の設定を流す
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        # WAL：読み込みと書き込みが同時に起きても待たされにくくなる
        cur.execute("PRAGMA journal_mode=WAL")
        # 書き込みが重なったら、エラーにせず最大5秒待つ
        cur.execute("PRAGMA busy_timeout=5000")
        # SQLite は外部キーの制約が初期設定でオフなので、オンにする
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


engine = make_engine(settings.database_url)

# Session：DB とのやり取り1回分（トランザクション）の単位。
# expire_on_commit=False：commit 後も、取り出したオブジェクトの値をそのまま読めるようにする
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """API ごとに Session を1つ渡し、終わったら閉じる（FastAPI の依存性注入で使う）。"""
    with SessionLocal() as session:
        yield session


def get_now() -> datetime:
    """現在時刻（UTC）。

    API の中で datetime.now() を直接呼ばず、これを経由する。
    テストでは差し替えて「2026-11-23 の朝」のような日時を自由に作れるようにするため。
    """
    return datetime.now(UTC)
