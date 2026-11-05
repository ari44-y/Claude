"""戸田市 中町1丁目のゴミ出しを、定期タスクと休止日として登録する（要件定義書 2.1）。

使い方（backend フォルダで、alembic upgrade head の後に）：
  uv run python -m app.tasks.seed_gomi

何度実行しても同じ内容が二重に登録されることはない。
毎年4月に収集日一覧表が出たら、SKIP_DATES にその年度の休止日を書き足して再実行する。
"""

from datetime import date, time

from sqlalchemy import select

from app.db import SessionLocal, get_now
from app.tasks import service
from app.tasks.models import SkipDate, TaskTemplate
from app.tasks.schemas import SkipDateCreate, TemplateCreate

GROUP = "gomi"
DUE = time(8, 0)  # 収集日当日の朝8時まで
START = date(2026, 4, 1)  # 令和8年度の始まり

TEMPLATES = [
    ("もやすごみ", "FREQ=WEEKLY;BYDAY=WE,SA"),
    ("もやさないごみ", "FREQ=WEEKLY;BYDAY=TU"),
    ("資源物", "FREQ=WEEKLY;BYDAY=MO"),
]

# 出典：戸田市「令和8年度版 ごみ収集日一覧表」
SKIP_DATES = [
    (date(2026, 11, 23), date(2026, 11, 23), "勤労感謝の日"),
    (date(2026, 12, 31), date(2027, 1, 3), "年末年始"),
]


def main() -> None:
    today = service.local_today(get_now())
    with SessionLocal() as session:
        # 休止日を先に登録する（テンプレートを登録した瞬間に回が作られるため）
        for start, end, note in SKIP_DATES:
            exists = session.scalar(
                select(SkipDate).where(SkipDate.skip_group == GROUP, SkipDate.start_date == start)
            )
            if exists:
                print(f"登録済み：休止日 {start}〜{end}")
                continue
            data = SkipDateCreate(skip_group=GROUP, start_date=start, end_date=end, note=note)
            service.create_skip_date(session, data, today)
            print(f"登録：休止日 {start}〜{end}（{note}）")

        for title, rule in TEMPLATES:
            if session.scalar(select(TaskTemplate).where(TaskTemplate.title == title)):
                print(f"登録済み：{title}")
                continue
            data = TemplateCreate(
                title=title, rrule=rule, dtstart=START, due_time=DUE, skip_group=GROUP
            )
            service.create_template(session, data, today)
            print(f"登録：{title}（{rule}）")


if __name__ == "__main__":
    main()
