"""タスク管理の処理の中身。

router.py（API の入口）から呼ばれる。HTTP のこと（ステータスコードなど）はここでは扱わず、
「DB をどう読み書きするか」だけを書く。こうしておくと、スケジューラーからも同じ関数を呼べる。

現在時刻 now と今日の日付 today は、すべて引数で受け取る（関数の中で datetime.now() を呼ばない）。
テストで「2026-11-23 の朝」を自由に作れるようにするため。
"""

from datetime import date, datetime, time

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.config import TZ, settings
from app.tasks.models import SkipDate, TaskInstance, TaskTemplate
from app.tasks.recurrence import date_range, is_skipped, occurrences
from app.tasks.schemas import (
    InstanceRead,
    SkipDateCreate,
    TaskCreate,
    TaskList,
    TemplateCreate,
    TemplateUpdate,
)

# ---------- 日時の小道具 ----------


def local_today(now: datetime) -> date:
    """UTC の現在時刻から、日本時間の「今日」の日付を出す。

    例：UTC 2026-11-04 23:30 は、日本時間では 2026-11-05 8:30 → 今日は 11/5
    """
    return now.astimezone(TZ).date()


def due_at_for(day: date, due_time: time | None) -> datetime | None:
    """日付と期限の時刻（日本時間）から、期限の日時を作る。時刻がなければ None。"""
    if due_time is None:
        return None
    return datetime.combine(day, due_time, tzinfo=TZ)


def is_overdue(inst: TaskInstance, now: datetime) -> bool:
    """期限切れかどうか。

    - 期限の日時があるもの：その日時を過ぎて未完了
    - 日付だけのもの：その日が終わって（翌日になって）も未完了
    """
    if inst.done_at is not None:
        return False
    if inst.due_at is not None:
        return inst.due_at < now
    if inst.scheduled_date is not None:
        return inst.scheduled_date < local_today(now)
    return False  # 期限なしの単発タスクは期限切れにならない


def _overdue_condition(now: datetime):
    """is_overdue() と同じ判定を、SQL の WHERE 条件として書いたもの。"""
    return and_(
        TaskInstance.done_at.is_(None),
        or_(
            and_(TaskInstance.due_at.is_not(None), TaskInstance.due_at < now),
            and_(
                TaskInstance.due_at.is_(None),
                TaskInstance.scheduled_date < local_today(now),
            ),
        ),
    )


# ---------- 定期タスクの回の生成 ----------


def _skip_ranges(session: Session, group: str | None) -> list[tuple[date, date]]:
    if group is None:
        return []
    rows = session.execute(
        select(SkipDate.start_date, SkipDate.end_date).where(SkipDate.skip_group == group)
    )
    return [(start, end) for start, end in rows]


def generate_for_template(session: Session, template: TaskTemplate, today: date, days: int) -> int:
    """1つのテンプレートについて、today から days 日先までの回を作る。作った数を返す。

    すでにある日は作らない（何度呼んでも結果が同じになる＝冪等）。
    """
    if not template.active:
        return 0

    start, end = date_range(today, days)
    days_in_rule = occurrences(template.rrule, template.dtstart, start, end)
    skips = _skip_ranges(session, template.skip_group)

    # session.scalars(...)：1列だけの結果を、値の並びとして受け取る
    existing = set(
        session.scalars(
            select(TaskInstance.scheduled_date).where(
                TaskInstance.template_id == template.id,
                TaskInstance.scheduled_date.between(start, end),
            )
        )
    )

    created = 0
    for day in days_in_rule:
        if day in existing or is_skipped(day, skips):
            continue
        session.add(
            TaskInstance(
                template_id=template.id,
                title=template.title,
                scheduled_date=day,
                due_at=due_at_for(day, template.due_time),
            )
        )
        created += 1
    return created


def generate_instances(session: Session, today: date, days: int | None = None) -> int:
    """有効なすべてのテンプレートについて回を作る。スケジューラーから毎日呼ばれる。"""
    days = settings.generate_days_ahead if days is None else days
    templates = session.scalars(select(TaskTemplate).where(TaskTemplate.active.is_(True)))
    created = sum(generate_for_template(session, t, today, days) for t in templates)
    session.commit()
    return created


def _delete_future_undone(session: Session, template_id: int, today: date) -> None:
    """そのテンプレートの、今日以降の未完了の回を消す（作り直しの前に使う）。

    完了済みの回と、過去の回（期限切れのものを含む）は履歴として残す。
    """
    session.execute(
        delete(TaskInstance).where(
            TaskInstance.template_id == template_id,
            TaskInstance.done_at.is_(None),
            TaskInstance.scheduled_date >= today,
        )
    )


# ---------- 定期タスク（テンプレート）の登録・変更・削除 ----------


def create_template(session: Session, data: TemplateCreate, today: date) -> TaskTemplate:
    # model_dump()：Pydantic のデータを dict にする。**で展開してテーブルのクラスに渡す
    template = TaskTemplate(**data.model_dump())
    session.add(template)
    session.flush()  # flush：commit の前に INSERT だけ実行して、template.id を確定させる
    generate_for_template(session, template, today, settings.generate_days_ahead)
    session.commit()
    return template


# None を入れられない列。TemplateUpdate で null が送られてきても無視する
_NOT_NULLABLE = {"title", "rrule", "dtstart", "active"}


def update_template(
    session: Session, template: TaskTemplate, data: TemplateUpdate, today: date
) -> TaskTemplate:
    # exclude_unset=True：画面が送ってこなかった項目は含めない。
    # 「due_time を送らなかった」と「due_time に null を送った（期限なしにしたい）」を区別できる
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is None and key in _NOT_NULLABLE:
            continue
        setattr(template, key, value)

    # ルールや期限が変わったかもしれないので、今日以降の未完了の回を作り直す
    _delete_future_undone(session, template.id, today)
    session.flush()
    generate_for_template(session, template, today, settings.generate_days_ahead)
    session.commit()
    return template


def delete_template(session: Session, template: TaskTemplate, today: date) -> None:
    _delete_future_undone(session, template.id, today)
    # 残った回（完了済み・過去分）の template_id は、外部キーの設定（SET NULL）で NULL になる
    session.delete(template)
    session.commit()


# ---------- 各回のタスク ----------


def to_read(inst: TaskInstance, now: datetime) -> InstanceRead:
    """DB のオブジェクトを、API で返す形に変換する（is_overdue を計算して入れる）。"""
    return InstanceRead.model_validate(inst).model_copy(
        update={"is_overdue": is_overdue(inst, now)}
    )


def list_tasks(session: Session, now: datetime, day: date) -> TaskList:
    """day の日のタスク一覧。次のものを返す。

    1. day の日の回（完了済みも含む。チェックを付けたものが消えないように）
    2. 期限切れの未完了の回（何日前のものでも。放置しにくくするため）
    3. 期限なしの単発タスクのうち、未完了のものと、day に完了したもの
    """
    day_start = datetime.combine(day, time.min, tzinfo=TZ)
    rows = session.scalars(
        select(TaskInstance).where(
            or_(
                TaskInstance.scheduled_date == day,
                _overdue_condition(now),
                and_(
                    TaskInstance.scheduled_date.is_(None),
                    or_(TaskInstance.done_at.is_(None), TaskInstance.done_at >= day_start),
                ),
            )
        )
    ).all()

    items = [to_read(inst, now) for inst in rows]

    # 並べ方：期限切れ → 期限の早い順 → 期限なし（追加した順）
    far_future = datetime.max.replace(tzinfo=TZ)

    def sort_key(item: InstanceRead):
        if item.due_at is not None:
            when = item.due_at
        elif item.scheduled_date is not None:
            when = datetime.combine(item.scheduled_date, time.max, tzinfo=TZ)
        else:
            when = far_future
        return (not item.is_overdue, when, item.id)

    items.sort(key=sort_key)
    return TaskList(items=items, overdue_count=sum(i.is_overdue for i in items))


def create_single(session: Session, data: TaskCreate) -> TaskInstance:
    """単発タスクを追加する。期限があれば、その日（日本時間）の回として扱う。"""
    inst = TaskInstance(
        title=data.title,
        due_at=data.due_at,
        scheduled_date=local_today(data.due_at) if data.due_at else None,
    )
    session.add(inst)
    session.commit()
    return inst


def update_instance(
    session: Session, inst: TaskInstance, done: bool | None, title: str | None, now: datetime
) -> TaskInstance:
    if done is True and inst.done_at is None:
        inst.done_at = now
    elif done is False:
        inst.done_at = None
    if title is not None:
        inst.title = title
    session.commit()
    return inst


class CannotDeleteRecurring(Exception):
    """定期タスクの回は消せない（消しても、次の生成で作り直されてしまうため）。"""


def delete_instance(session: Session, inst: TaskInstance) -> None:
    if inst.template_id is not None:
        raise CannotDeleteRecurring
    session.delete(inst)
    session.commit()


# ---------- 休止日 ----------


def create_skip_date(session: Session, data: SkipDateCreate, today: date) -> SkipDate:
    skip = SkipDate(**data.model_dump())
    session.add(skip)

    # すでに作ってしまった、休止日に当たる未完了の回を消す
    template_ids = select(TaskTemplate.id).where(TaskTemplate.skip_group == data.skip_group)
    session.execute(
        delete(TaskInstance).where(
            TaskInstance.template_id.in_(template_ids),
            TaskInstance.done_at.is_(None),
            TaskInstance.scheduled_date.between(max(data.start_date, today), data.end_date),
        )
    )
    session.commit()
    return skip


def delete_skip_date(session: Session, skip: SkipDate, today: date) -> None:
    session.delete(skip)
    session.flush()
    # 休止日でなくなった日の回を作る
    generate_instances(session, today)
