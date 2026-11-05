"""タスク管理のテーブル定義（SQLAlchemy 2.0 の書き方）。

定期タスクは「繰り返しのルール（TaskTemplate）」と「各回の実体（TaskInstance）」に分けて持つ。
完了チェックは各回に付ける（要件定義書 6.1）。
"""

from datetime import UTC, date, datetime, time

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TaskTemplate(Base):
    """定期タスクの定義。例：燃えるゴミ／毎週水・土／期限 8:00／休止日グループ gomi"""

    __tablename__ = "task_templates"

    # Mapped[int]：Python 側の型。mapped_column(...)：DB 側の列の設定
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))

    # 繰り返しのルール。RFC 5545（カレンダーの標準規格）の RRULE 形式の文字列
    #   毎週水・土     → FREQ=WEEKLY;BYDAY=WE,SA
    #   第2・第4水曜   → FREQ=MONTHLY;BYDAY=2WE,4WE
    #   3日おき        → FREQ=DAILY;INTERVAL=3
    rrule: Mapped[str] = mapped_column(String(200))

    # 繰り返しの起点日。「3日おき」の数え始めはこの日になる
    dtstart: Mapped[date]

    # 期限の時刻（日本時間）。None なら「その日のうち」
    # Mapped[time | None] のように None を含めると、DB の列も NULL 可になる
    due_time: Mapped[time | None]

    # 休止日のグループ名。"gomi" なら、グループ gomi の休止日には回を作らない
    skip_group: Mapped[str | None] = mapped_column(String(50))

    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_utcnow)

    # このテンプレートから作られた回の一覧（Python から template.instances で辿れる）
    instances: Mapped[list["TaskInstance"]] = relationship(back_populates="template")


class TaskInstance(Base):
    """1回分のタスク。定期タスクの各回と、単発タスクの両方をこのテーブルで持つ。"""

    __tablename__ = "task_instances"
    __table_args__ = (
        # 同じテンプレートの同じ日の回は1つだけ。
        # 生成処理が何度走っても、二重に作られないようにする安全装置。
        # （単発タスクは template_id が NULL。SQLite は NULL どうしを別物と扱うので制約にかからない）
        UniqueConstraint("template_id", "scheduled_date", name="uq_instance_template_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # 単発タスクは None。テンプレートを消しても、完了済みの履歴は残す（SET NULL）
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_templates.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(100))

    # その回の日付（日本時間の日付）。期限なしの単発タスクは None
    scheduled_date: Mapped[date | None]

    # 期限の日時（UTC で保存）。時刻の決まっていないタスクは None
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    # 完了した日時。None なら未完了
    done_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_utcnow)

    template: Mapped[TaskTemplate | None] = relationship(back_populates="instances")


class SkipDate(Base):
    """休止日。例：グループ gomi／2026-12-31〜2027-01-03／年末年始

    戸田市の収集日一覧は年度ごとに出るので、毎年4月にその年度の分を登録する。
    """

    __tablename__ = "skip_dates"

    id: Mapped[int] = mapped_column(primary_key=True)
    skip_group: Mapped[str] = mapped_column(String(50), index=True)
    start_date: Mapped[date]
    end_date: Mapped[date]  # 1日だけなら start_date と同じ日
    note: Mapped[str | None] = mapped_column(String(100))
