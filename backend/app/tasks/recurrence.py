"""繰り返しの計算。

DB を使わない「日付を入れたら日付が返る」だけの関数にしてある。
こうしておくと、テストで DB を用意せずに「第2・第4水曜」などを確かめられる。
"""

import re
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta

from dateutil.rrule import rrulestr

# 許可する繰り返しの単位。SECONDLY などを入れられると、2週間分でも膨大な回ができてしまう
_ALLOWED_FREQ = re.compile(r"(^|;)FREQ=(DAILY|WEEKLY|MONTHLY|YEARLY)(;|$)")


def validate_rrule(rule: str) -> str:
    """ルールの文字列を確かめ、問題なければそのまま返す。おかしければ ValueError。"""
    rule = rule.strip().upper()
    if "DTSTART" in rule:
        # 起点日は dtstart 列で別に持つ。文字列の中にも書けると、どちらが正しいか分からなくなる
        raise ValueError("DTSTART はルールに含めず、dtstart で指定してください")
    if not _ALLOWED_FREQ.search(rule):
        raise ValueError("FREQ は DAILY / WEEKLY / MONTHLY / YEARLY のいずれかにしてください")
    try:
        rrulestr(rule, dtstart=datetime(2000, 1, 1))
    except (ValueError, TypeError) as e:
        raise ValueError(f"繰り返しのルールが読めません：{e}") from e
    return rule


def occurrences(rule: str, dtstart: date, start: date, end: date) -> list[date]:
    """ルールに当てはまる日のうち、start〜end（両端を含む）のものを返す。

    例：occurrences("FREQ=WEEKLY;BYDAY=WE,SA", date(2026,1,1), date(2026,11,1), date(2026,11,7))
        → [2026-11-04(水), 2026-11-07(土)]
    """
    # dateutil は datetime で計算するので、日付を「その日の 0:00」に変換して渡す
    r = rrulestr(rule, dtstart=datetime.combine(dtstart, time.min))
    hits = r.between(
        datetime.combine(start, time.min),
        datetime.combine(end, time.min),
        inc=True,  # start・end ちょうどの日も含める
    )
    return [d.date() for d in hits]


def is_skipped(day: date, ranges: Iterable[tuple[date, date]]) -> bool:
    """day が休止日の期間（start〜end、両端を含む）のどれかに入っていれば True。"""
    return any(start <= day <= end for start, end in ranges)


def date_range(start: date, days: int) -> tuple[date, date]:
    """start から days 日先までの期間（両端を含む）。"""
    return start, start + timedelta(days=days)
