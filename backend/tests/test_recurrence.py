"""繰り返しの計算のテスト（DB を使わない）。

要件定義書 2.1 の「繰り返しルール」の5パターンと、ゴミ出しの休止日を確かめる。
"""

from datetime import date

import pytest

from app.tasks.recurrence import is_skipped, occurrences, validate_rrule

NOV_START = date(2026, 11, 1)
NOV_END = date(2026, 11, 30)


def test_daily():
    days = occurrences("FREQ=DAILY", date(2026, 1, 1), date(2026, 11, 1), date(2026, 11, 3))
    assert days == [date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3)]


def test_weekly_multiple_weekdays():
    # 毎週 月・木
    days = occurrences("FREQ=WEEKLY;BYDAY=MO,TH", date(2026, 1, 1), NOV_START, date(2026, 11, 14))
    assert days == [date(2026, 11, 2), date(2026, 11, 5), date(2026, 11, 9), date(2026, 11, 12)]


def test_monthly_nth_weekday():
    # 第2・第4水曜。2026年11月の水曜は 4, 11, 18, 25 日
    days = occurrences("FREQ=MONTHLY;BYDAY=2WE,4WE", date(2026, 1, 1), NOV_START, NOV_END)
    assert days == [date(2026, 11, 11), date(2026, 11, 25)]


def test_every_n_days_counts_from_dtstart():
    # 3日おき。起点日（dtstart）から数える
    days = occurrences("FREQ=DAILY;INTERVAL=3", date(2026, 11, 2), NOV_START, date(2026, 11, 12))
    assert days == [date(2026, 11, 2), date(2026, 11, 5), date(2026, 11, 8), date(2026, 11, 11)]


def test_monthly_day_of_month():
    days = occurrences("FREQ=MONTHLY;BYMONTHDAY=25", date(2026, 1, 1), NOV_START, date(2027, 1, 31))
    assert days == [date(2026, 11, 25), date(2026, 12, 25), date(2027, 1, 25)]


def test_nothing_before_dtstart():
    # 起点日より前の日は出てこない
    days = occurrences("FREQ=DAILY", date(2026, 11, 10), NOV_START, date(2026, 11, 11))
    assert days == [date(2026, 11, 10), date(2026, 11, 11)]


def test_gomi_skip_on_labor_thanksgiving_day():
    # 資源物（毎週月）。11/23（勤労感謝の日・月曜）は休み
    skips = [(date(2026, 11, 23), date(2026, 11, 23))]
    days = occurrences("FREQ=WEEKLY;BYDAY=MO", date(2026, 4, 1), NOV_START, NOV_END)
    kept = [d for d in days if not is_skipped(d, skips)]
    assert date(2026, 11, 23) in days
    assert kept == [date(2026, 11, 2), date(2026, 11, 9), date(2026, 11, 16), date(2026, 11, 30)]


def test_is_skipped_range_includes_both_ends():
    new_year = [(date(2026, 12, 31), date(2027, 1, 3))]
    assert is_skipped(date(2026, 12, 31), new_year)
    assert is_skipped(date(2027, 1, 3), new_year)
    assert not is_skipped(date(2026, 12, 30), new_year)
    assert not is_skipped(date(2027, 1, 4), new_year)


def test_validate_rrule_normalizes_case():
    assert validate_rrule(" freq=weekly;byday=we,sa ") == "FREQ=WEEKLY;BYDAY=WE,SA"


@pytest.mark.parametrize(
    "rule",
    [
        "FREQ=SECONDLY",  # 細かすぎる繰り返しは禁止
        "DTSTART:20260101\nRRULE:FREQ=DAILY",  # 起点日は別の列で持つ
        "BYDAY=MO",  # FREQ がない
        "FREQ=WEEKLY;BYDAY=XX",  # 曜日が読めない
    ],
)
def test_validate_rrule_rejects(rule):
    # pytest.raises：中の処理が、この例外を投げることを確かめる
    with pytest.raises(ValueError):
        validate_rrule(rule)
