"""タスク管理 API のテスト。

TestClient で実際に API を呼び、DB の中身や返り値を確かめる。
時刻は clock.set(...) で日本時間を指定する（conftest.py 参照）。
"""

from datetime import date

from sqlalchemy import func, select

from app.tasks.models import TaskInstance
from app.tasks.service import generate_instances

MOYASU = {  # もやすごみ：毎週 水・土、当日 8:00 まで、休止日グループ gomi
    "title": "もやすごみ",
    "rrule": "FREQ=WEEKLY;BYDAY=WE,SA",
    "dtstart": "2026-04-01",
    "due_time": "08:00",
    "skip_group": "gomi",
}


def _dates(client, day: str) -> list[str]:
    return [t["scheduled_date"] for t in client.get(f"/api/tasks?date={day}").json()["items"]]


def _count(session) -> int:
    return session.scalar(select(func.count()).select_from(TaskInstance))


# ---------- 定期タスクの生成 ----------


def test_create_template_generates_two_weeks(client, clock, session):
    clock.set(2026, 11, 5, 12, 0)  # 木曜
    res = client.post("/api/task-templates", json=MOYASU)
    assert res.status_code == 201

    days = session.scalars(select(TaskInstance.scheduled_date).order_by("scheduled_date")).all()
    # 11/5〜11/19 の水・土
    assert days == [
        date(2026, 11, 7),
        date(2026, 11, 11),
        date(2026, 11, 14),
        date(2026, 11, 18),
    ]


def test_due_at_is_8am_japan_time_returned_as_utc(client, clock):
    clock.set(2026, 11, 7, 6, 0)
    client.post("/api/task-templates", json=MOYASU)
    task = client.get("/api/tasks?date=2026-11-07").json()["items"][0]
    # 日本時間 11/7 8:00 ＝ UTC 11/6 23:00
    assert task["due_at"] == "2026-11-06T23:00:00Z"


def test_generate_is_idempotent(client, clock, session):
    clock.set(2026, 11, 5, 12, 0)
    client.post("/api/task-templates", json=MOYASU)
    before = _count(session)
    # もう一度生成しても、同じ回は作られない
    assert generate_instances(session, date(2026, 11, 5)) == 0
    assert _count(session) == before


def test_new_year_holidays_are_skipped(client, clock, session):
    clock.set(2026, 12, 20, 12, 0)
    client.post(
        "/api/skip-dates",
        json={"skip_group": "gomi", "start_date": "2026-12-31", "end_date": "2027-01-03"},
    )
    client.post("/api/task-templates", json=MOYASU)
    clock.set(2026, 12, 28, 0, 10)
    generate_instances(session, date(2026, 12, 28))

    days = set(session.scalars(select(TaskInstance.scheduled_date)))
    assert date(2026, 12, 30) in days  # 水
    assert date(2027, 1, 2) not in days  # 土だが年末年始の休み
    assert date(2027, 1, 6) in days  # 水


def test_skip_group_only_affects_its_own_templates(client, clock, session):
    clock.set(2026, 11, 20, 12, 0)
    client.post(
        "/api/skip-dates",
        json={"skip_group": "gomi", "start_date": "2026-11-23", "end_date": "2026-11-23"},
    )
    client.post(
        "/api/task-templates", json={**MOYASU, "title": "資源物", "rrule": "FREQ=WEEKLY;BYDAY=MO"}
    )
    client.post(
        "/api/task-templates",
        json={"title": "洗濯", "rrule": "FREQ=DAILY", "dtstart": "2026-01-01"},
    )
    titles_on_23 = [t["title"] for t in client.get("/api/tasks?date=2026-11-23").json()["items"]]
    assert titles_on_23 == ["洗濯"]  # 資源物は休み、洗濯（グループなし）は通常どおり


def test_adding_skip_date_removes_generated_instances(client, clock):
    clock.set(2026, 11, 20, 12, 0)
    client.post("/api/task-templates", json={**MOYASU, "rrule": "FREQ=WEEKLY;BYDAY=MO"})
    assert _dates(client, "2026-11-23") == ["2026-11-23"]

    res = client.post(
        "/api/skip-dates",
        json={"skip_group": "gomi", "start_date": "2026-11-23", "end_date": "2026-11-23"},
    )
    assert _dates(client, "2026-11-23") == []

    # 休止日を消すと、また作られる
    client.delete(f"/api/skip-dates/{res.json()['id']}")
    assert _dates(client, "2026-11-23") == ["2026-11-23"]


def test_update_template_regenerates_but_keeps_done(client, clock, session):
    clock.set(2026, 11, 7, 7, 0)  # 土曜の朝
    tpl = client.post("/api/task-templates", json=MOYASU).json()
    today = client.get("/api/tasks").json()["items"][0]
    client.patch(f"/api/task-instances/{today['id']}", json={"done": True})

    # 水・土 → 火 に変更
    client.patch(f"/api/task-templates/{tpl['id']}", json={"rrule": "FREQ=WEEKLY;BYDAY=TU"})

    rows = session.execute(
        select(TaskInstance.scheduled_date, TaskInstance.done_at).order_by("scheduled_date")
    ).all()
    days = [d for d, _ in rows]
    assert days[0] == date(2026, 11, 7)  # 完了済みの今日の回は残る
    assert rows[0].done_at is not None
    assert days[1:] == [date(2026, 11, 10), date(2026, 11, 17)]  # 以降は火曜で作り直し


def test_delete_template_keeps_done_history(client, clock, session):
    clock.set(2026, 11, 7, 7, 0)
    tpl = client.post("/api/task-templates", json=MOYASU).json()
    today = client.get("/api/tasks").json()["items"][0]
    client.patch(f"/api/task-instances/{today['id']}", json={"done": True})

    assert client.delete(f"/api/task-templates/{tpl['id']}").status_code == 204
    remaining = session.scalars(select(TaskInstance)).all()
    assert len(remaining) == 1
    assert remaining[0].template_id is None  # SET NULL で履歴だけ残る


def test_invalid_rrule_returns_422(client):
    res = client.post("/api/task-templates", json={**MOYASU, "rrule": "FREQ=SECONDLY"})
    assert res.status_code == 422


# ---------- 一覧・期限切れ・完了 ----------


def test_overdue_listed_first_and_counted(client, clock):
    clock.set(2026, 11, 7, 6, 0)
    client.post("/api/task-templates", json=MOYASU)
    client.post("/api/tasks", json={"title": "牛乳を買う"})

    clock.set(2026, 11, 7, 8, 30)  # 8:00 を過ぎた
    body = client.get("/api/tasks").json()
    assert body["overdue_count"] == 1
    assert body["items"][0]["title"] == "もやすごみ"
    assert body["items"][0]["is_overdue"] is True
    assert body["items"][1]["title"] == "牛乳を買う"

    # 次の日も、未完了なら期限切れとして出続ける
    clock.set(2026, 11, 8, 9, 0)
    body = client.get("/api/tasks").json()
    assert [t["title"] for t in body["items"]] == ["もやすごみ", "牛乳を買う"]

    # 完了すると期限切れではなくなる
    client.patch(f"/api/task-instances/{body['items'][0]['id']}", json={"done": True})
    assert client.get("/api/tasks").json()["overdue_count"] == 0


def test_today_is_japan_date(client, clock):
    # 日本時間 11/7 0:30 は、UTC ではまだ 11/6。「今日」は日本時間の 11/7 になる
    clock.set(2026, 11, 7, 0, 30)
    client.post("/api/task-templates", json=MOYASU)
    assert _dates(client, "2026-11-07") == ["2026-11-07"]
    assert [t["scheduled_date"] for t in client.get("/api/tasks").json()["items"]] == ["2026-11-07"]


def test_single_task_without_due_disappears_day_after_done(client, clock):
    clock.set(2026, 11, 5, 10, 0)
    task = client.post("/api/tasks", json={"title": "電球を替える"}).json()
    assert task["scheduled_date"] is None

    client.patch(f"/api/task-instances/{task['id']}", json={"done": True})
    assert len(client.get("/api/tasks").json()["items"]) == 1  # 完了した当日は残る

    clock.set(2026, 11, 6, 10, 0)
    assert client.get("/api/tasks").json()["items"] == []  # 翌日には消える


def test_single_task_with_due_uses_japan_date(client):
    task = client.post(
        "/api/tasks", json={"title": "書類を出す", "due_at": "2026-11-10T00:30:00+09:00"}
    ).json()
    assert task["scheduled_date"] == "2026-11-10"
    assert task["due_at"] == "2026-11-09T15:30:00Z"


def test_due_at_without_timezone_is_rejected(client):
    res = client.post("/api/tasks", json={"title": "x", "due_at": "2026-11-10T18:00:00"})
    assert res.status_code == 422


def test_undo_done(client):
    task = client.post("/api/tasks", json={"title": "x"}).json()
    client.patch(f"/api/task-instances/{task['id']}", json={"done": True})
    res = client.patch(f"/api/task-instances/{task['id']}", json={"done": False})
    assert res.json()["done_at"] is None


def test_cannot_delete_recurring_instance(client, clock):
    clock.set(2026, 11, 7, 6, 0)
    client.post("/api/task-templates", json=MOYASU)
    inst = client.get("/api/tasks").json()["items"][0]
    assert client.delete(f"/api/task-instances/{inst['id']}").status_code == 409

    single = client.post("/api/tasks", json={"title": "x"}).json()
    assert client.delete(f"/api/task-instances/{single['id']}").status_code == 204


def test_not_found(client):
    assert client.patch("/api/task-instances/999", json={"done": True}).status_code == 404
