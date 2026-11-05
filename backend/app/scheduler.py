"""定期的に動く処理（APScheduler）。

FastAPI と同じプロセスの中で動かす。プロセスを分けると、
SQLite への書き込みが2か所から起きて待たされやすくなるため（要件定義書 6章）。

今あるジョブ：
- 毎日 0:05 定期タスクの回を2週間先まで作る
（通知の送信（1分ごと）は Phase 1 の手順4で追加する）
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import TZ
from app.db import SessionLocal, get_now
from app.tasks.service import generate_instances, local_today

logger = logging.getLogger(__name__)


def run_generate(now: datetime | None = None) -> int:
    """定期タスクの回を作る。起動時と毎日 0:05 に呼ばれる。"""
    now = now or get_now()
    with SessionLocal() as session:
        created = generate_instances(session, local_today(now))
    logger.info("定期タスクの回を %d 件作りました", created)
    return created


def create_scheduler() -> AsyncIOScheduler:
    # timezone=TZ：「0:05」を日本時間として扱う（サーバーの OS の設定に左右されない）
    scheduler = AsyncIOScheduler(timezone=TZ)

    # 普通の関数（async でない関数）を登録すると、APScheduler は別スレッドで実行する。
    # そのため DB の処理に少し時間がかかっても、API の応答は止まらない。
    scheduler.add_job(
        run_generate,
        "cron",
        hour=0,
        minute=5,
        id="generate_instances",
        # サーバーが止まっていて 0:05 を逃しても、1時間以内に起動すれば1回だけ実行する
        misfire_grace_time=3600,
        coalesce=True,
    )
    return scheduler
