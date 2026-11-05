"""アプリの起動口。

開発時：  cd backend && uv run uvicorn app.main:app --reload
サーバー：uvicorn app.main:app --workers 1（2つにするとスケジューラーも2つ動き、通知が二重になる）

frontend/dist（npm run build の結果）があれば、画面もここから配信する（app/frontend.py）。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.frontend import mount_frontend
from app.scheduler import create_scheduler, run_generate
from app.tasks.router import router as tasks_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """起動時と終了時の処理。yield の前が起動時、後が終了時。"""
    scheduler = None
    if settings.scheduler_enabled:
        # 起動時にも1回作る。サーバーが止まっていた間の生成漏れを埋めるため
        run_generate()
        scheduler = create_scheduler()
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown()


app = FastAPI(title="クロコさん API", lifespan=lifespan)
app.include_router(tasks_router)


@app.get("/api/health")
def health():
    """動いているかの確認用。"""
    return {"status": "ok"}


# 画面の配信は、すべての API を登録した後に（frontend.py の説明を参照）
mount_frontend(app, settings.frontend_dist)
