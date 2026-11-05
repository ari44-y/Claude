"""アプリ全体の設定。

値は環境変数か backend/.env から読む。.env は Git に入れない（.gitignore 済み）。
サーバーでは .env に DATABASE_URL=sqlite:////var/lib/kuroko/kuroko.db のように書く。
"""

from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

# 画面の表示・繰り返しの計算はすべて日本時間で行う（DB への保存は UTC）。
# サーバーの OS の設定に左右されないよう、コードで明示する。
TZ = ZoneInfo("Asia/Tokyo")


class Settings(BaseSettings):
    # env_file：.env を読む。環境変数が設定されていれば、そちらが優先される
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite の URL。「sqlite:///」の後ろは相対パス、「sqlite:////」なら絶対パス
    database_url: str = "sqlite:///./data/kuroko.db"

    # 定期タスクの回を、今日から何日先まで作っておくか
    generate_days_ahead: int = 14

    # False にするとスケジューラーを起動しない（テストで使う）
    scheduler_enabled: bool = True

    # React のビルド結果のフォルダ（npm run build で作られる）。初期値はリポジトリの frontend/dist
    frontend_dist: Path = Path(__file__).resolve().parents[2] / "frontend" / "dist"


settings = Settings()
