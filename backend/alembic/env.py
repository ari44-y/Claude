"""Alembic の実行設定。

使い方（backend フォルダで）：
  テーブルを変えたら   uv run alembic revision --autogenerate -m "変更の説明"
  DB に反映する        uv run alembic upgrade head

接続先は alembic.ini ではなく、アプリと同じ設定（app/config.py の database_url）を使う。
"""

from logging.config import fileConfig

from alembic import context

import app.tasks.models  # noqa: F401  テーブル定義を読み込んで Base.metadata に登録させる
from app.db import Base, engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate はこの metadata（＝ models.py の定義）と実際の DB を比べて、差分を見つける
target_metadata = Base.metadata


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite は「列の型を変える」「列を消す」などの ALTER TABLE がほとんどできない。
            # batch モードにすると、Alembic が「新しい表を作ってコピーして入れ替える」方法で変更してくれる
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("オフラインモード（SQL の書き出し）は使いません")
run_migrations_online()
