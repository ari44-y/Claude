"""タスク管理の API の入口。

ここでは「URL」「受け取る値」「返すステータスコード」だけを扱い、
処理の中身は service.py に任せる。
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db, get_now
from app.tasks import service
from app.tasks.models import SkipDate, TaskInstance, TaskTemplate
from app.tasks.schemas import (
    InstanceRead,
    InstanceUpdate,
    SkipDateCreate,
    SkipDateRead,
    TaskCreate,
    TaskList,
    TemplateCreate,
    TemplateRead,
    TemplateUpdate,
)

router = APIRouter(prefix="/api", tags=["tasks"])

# 依存性注入（Depends）：
# 引数に「db: DB」と書くだけで、FastAPI が get_db() を呼んで Session を渡してくれる。
# テストでは get_db・get_now を差し替えられる（tests/conftest.py 参照）。
DB = Annotated[Session, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]


def _get_or_404(db: Session, model, obj_id: int):
    obj = db.get(model, obj_id)  # 主キーで1件取り出す。なければ None
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "見つかりません")
    return obj


# ---------- 各回のタスク ----------


@router.get("/tasks", response_model=TaskList)
def list_tasks(db: DB, now: Now, day: Annotated[date | None, Query(alias="date")] = None):
    """その日のタスク一覧。?date=2026-11-05 のように指定する。省略すると今日（日本時間）。"""
    # 引数名を date にすると型の date と名前がぶつかるので、引数は day にして
    # URL 上の名前だけ alias で date にしている
    return service.list_tasks(db, now, day or service.local_today(now))


@router.post("/tasks", response_model=InstanceRead, status_code=status.HTTP_201_CREATED)
def create_task(data: TaskCreate, db: DB, now: Now):
    """単発タスクを追加する。"""
    inst = service.create_single(db, data)
    return service.to_read(inst, now)


@router.patch("/task-instances/{instance_id}", response_model=InstanceRead)
def update_instance(instance_id: int, data: InstanceUpdate, db: DB, now: Now):
    """完了チェックの切り替え・タイトルの変更。"""
    inst = _get_or_404(db, TaskInstance, instance_id)
    inst = service.update_instance(db, inst, data.done, data.title, now)
    return service.to_read(inst, now)


@router.delete("/task-instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_instance(instance_id: int, db: DB):
    """単発タスクを削除する。定期タスクの回は削除できない（409）。"""
    inst = _get_or_404(db, TaskInstance, instance_id)
    try:
        service.delete_instance(db, inst)
    except service.CannotDeleteRecurring:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "定期タスクの回は削除できません。不要ならテンプレートを変更してください",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- 定期タスク（テンプレート） ----------


@router.get("/task-templates", response_model=list[TemplateRead])
def list_templates(db: DB):
    return db.scalars(select(TaskTemplate).order_by(TaskTemplate.id)).all()


@router.post("/task-templates", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(data: TemplateCreate, db: DB, now: Now):
    """定期タスクを登録し、2週間先までの回をすぐに作る。"""
    return service.create_template(db, data, service.local_today(now))


@router.patch("/task-templates/{template_id}", response_model=TemplateRead)
def update_template(template_id: int, data: TemplateUpdate, db: DB, now: Now):
    template = _get_or_404(db, TaskTemplate, template_id)
    return service.update_template(db, template, data, service.local_today(now))


@router.delete("/task-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: int, db: DB, now: Now):
    template = _get_or_404(db, TaskTemplate, template_id)
    service.delete_template(db, template, service.local_today(now))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- 休止日 ----------


@router.get("/skip-dates", response_model=list[SkipDateRead])
def list_skip_dates(db: DB):
    return db.scalars(select(SkipDate).order_by(SkipDate.start_date)).all()


@router.post("/skip-dates", response_model=SkipDateRead, status_code=status.HTTP_201_CREATED)
def create_skip_date(data: SkipDateCreate, db: DB, now: Now):
    return service.create_skip_date(db, data, service.local_today(now))


@router.delete("/skip-dates/{skip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skip_date(skip_id: int, db: DB, now: Now):
    skip = _get_or_404(db, SkipDate, skip_id)
    service.delete_skip_date(db, skip, service.local_today(now))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
