"""画面とやり取りするデータの形（Pydantic）。

models.py が「DB にどう保存するか」なのに対し、こちらは「API で何を受け取り、何を返すか」。
分けておくと、DB の列を足しても API の形は勝手に変わらない。
FastAPI はこの定義から、入力のチェックと API 仕様書（/docs）を自動で作る。
"""

from datetime import UTC, date, datetime, time

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.tasks.recurrence import validate_rrule

# ---------- 定期タスク（テンプレート） ----------


class TemplateFields(BaseModel):
    """登録と返却で共通の項目。"""

    title: str = Field(min_length=1, max_length=100)
    rrule: str = Field(examples=["FREQ=WEEKLY;BYDAY=WE,SA"])
    dtstart: date
    due_time: time | None = Field(default=None, examples=["08:00"])
    skip_group: str | None = Field(default=None, examples=["gomi"])
    active: bool = True


class TemplateCreate(TemplateFields):
    # field_validator：その項目を受け取ったときに走るチェック。
    # ValueError を投げると、FastAPI が 422（入力エラー）としてメッセージ付きで返す
    @field_validator("rrule")
    @classmethod
    def _check_rrule(cls, v: str) -> str:
        return validate_rrule(v)


class TemplateUpdate(BaseModel):
    """変更したい項目だけを送る（送らなかった項目はそのまま）。"""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    rrule: str | None = None
    dtstart: date | None = None
    due_time: time | None = None
    skip_group: str | None = None
    active: bool | None = None

    @field_validator("rrule")
    @classmethod
    def _check_rrule(cls, v: str | None) -> str | None:
        return None if v is None else validate_rrule(v)


class TemplateRead(TemplateFields):
    # from_attributes=True：SQLAlchemy のオブジェクト（template.title など）から直接作れるようにする
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------- 各回のタスク ----------


class TaskCreate(BaseModel):
    """単発タスクの追加。"""

    title: str = Field(min_length=1, max_length=100)
    # AwareDatetime：「2026-11-10T18:00:00+09:00」のようにタイムゾーン付きの日時だけを受け付ける
    due_at: AwareDatetime | None = None


class InstanceUpdate(BaseModel):
    done: bool | None = None
    title: str | None = Field(default=None, min_length=1, max_length=100)


class InstanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int | None
    title: str
    scheduled_date: date | None
    due_at: datetime | None
    done_at: datetime | None
    # DB の列ではなく、返すときに計算して入れる値（service.py 参照）
    is_overdue: bool = False

    # 返す日時は必ず UTC にそろえる。
    # 追加した直後のオブジェクトは、受け取った「+09:00」のままメモリに残っているため、
    # そのまま返すと、DB から読み直したとき（UTC）と形式がずれてしまう
    @field_validator("due_at", "done_at")
    @classmethod
    def _to_utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else v.astimezone(UTC)


class TaskList(BaseModel):
    items: list[InstanceRead]
    # 期限切れの件数。ホーム画面アイコンのバッジに使う
    overdue_count: int


# ---------- 休止日 ----------


class SkipDateCreate(BaseModel):
    skip_group: str = Field(min_length=1, max_length=50, examples=["gomi"])
    start_date: date
    end_date: date
    note: str | None = Field(default=None, max_length=100)

    # model_validator(mode="after")：全項目がそろった後に走るチェック（項目どうしの関係を見る）
    @model_validator(mode="after")
    def _check_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date は start_date 以降にしてください")
        return self


class SkipDateRead(SkipDateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
