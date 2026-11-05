# 解説 01：バックエンドの土台とタスク API

Phase 1 の手順1「タスクの API と DB（単発タスク → 定期タスクと繰り返しの計算）」で作ったものの解説。
コードと一緒に読む前提で、「何をしているか」より「なぜそう書いたか」を中心に書く。

---

## 1. このステップで作ったもの

| ファイル | 役割 |
|---|---|
| [backend/pyproject.toml](../../backend/pyproject.toml) | 使うライブラリと、pytest・ruff の設定 |
| [backend/app/config.py](../../backend/app/config.py) | 設定（DB の場所など）とタイムゾーン |
| [backend/app/db.py](../../backend/app/db.py) | DB の接続、日時を UTC で保存する型、Session と現在時刻の受け渡し |
| [backend/app/tasks/models.py](../../backend/app/tasks/models.py) | テーブル定義（テンプレート・各回・休止日） |
| [backend/app/tasks/recurrence.py](../../backend/app/tasks/recurrence.py) | 繰り返しの計算（DB を使わない） |
| [backend/app/tasks/schemas.py](../../backend/app/tasks/schemas.py) | API で受け取る・返すデータの形 |
| [backend/app/tasks/service.py](../../backend/app/tasks/service.py) | 処理の中身（回の生成、一覧、期限切れの判定） |
| [backend/app/tasks/router.py](../../backend/app/tasks/router.py) | API の入口（URL とステータスコード） |
| [backend/app/scheduler.py](../../backend/app/scheduler.py) | 毎日 0:05 に回を作るジョブ |
| [backend/app/main.py](../../backend/app/main.py) | アプリの起動口 |
| [backend/app/tasks/seed_gomi.py](../../backend/app/tasks/seed_gomi.py) | 戸田市のゴミ出しを登録するスクリプト |
| [backend/alembic/](../../backend/alembic/) | DB の変更履歴 |
| [backend/tests/](../../backend/tests/) | テスト（30件） |

### API の一覧

| メソッド | URL | 内容 |
|---|---|---|
| GET | `/api/tasks?date=2026-11-05` | その日のタスク一覧（省略すると今日） |
| POST | `/api/tasks` | 単発タスクの追加 |
| PATCH | `/api/task-instances/{id}` | 完了チェック・タイトルの変更 |
| DELETE | `/api/task-instances/{id}` | 単発タスクの削除（定期タスクの回は 409） |
| GET / POST | `/api/task-templates` | 定期タスクの一覧・登録 |
| PATCH / DELETE | `/api/task-templates/{id}` | 定期タスクの変更・削除 |
| GET / POST | `/api/skip-dates` | 休止日の一覧・登録 |
| DELETE | `/api/skip-dates/{id}` | 休止日の削除 |
| GET | `/api/health` | 動作確認用 |

---

## 2. 動かしてみる

> **2026-11-05 追記：開発は Docker で行う構成に変えた**（[解説 03](03-Dockerでの開発と本番.md)）。
> 以下のコマンドは、`docker compose up` で起動したうえで、先頭に `docker compose exec backend` を付けて実行する。
> 例：`docker compose exec backend uv run pytest`。サーバーの起動（uvicorn）と DB の作成（alembic upgrade）は、`docker compose up` が自動で行う。

`backend` フォルダで実行する。

```bash
uv sync                                  # ライブラリを入れる（.venv が作られる）
uv run alembic upgrade head              # DB（backend/data/kuroko.db）にテーブルを作る
uv run python -m app.tasks.seed_gomi     # ゴミ出しの定期タスクと休止日を登録
uv run uvicorn app.main:app --reload     # サーバーを起動（コードを保存すると自動で再起動）
```

ブラウザで http://localhost:8000/docs を開くと、FastAPI が自動で作った API の画面が出る。
各 API の「Try it out」から、実際に呼び出して試せる。

```bash
uv run pytest            # テストを実行
uv run pytest -v         # テスト名を1件ずつ表示
uv run ruff check .      # 書き方のチェック
uv run ruff format .     # 自動で整形
```

> **`uv run` とは**：`.venv` の中の Python で実行するコマンド。`source .venv/bin/activate` をしなくても、
> いつもこのプロジェクト用の Python とライブラリで動く。

> **注意**：pyenv の Python 3.11 が有効になっていると、`VIRTUAL_ENV ... will be ignored` という警告が出る。
> uv はプロジェクトの `.venv`（Python 3.12）を正しく使っているので、無視してよい。

---

## 3. リクエストが来てから返るまで

`PATCH /api/task-instances/5`（完了チェック）を例にする。

```
画面 ──JSON {"done": true}──▶ router.py
                               │ ① schemas.InstanceUpdate で JSON をチェック（おかしければ 422）
                               │ ② Depends で Session と現在時刻を受け取る
                               │ ③ id=5 を DB から取り出す（なければ 404）
                               ▼
                             service.py
                               │ ④ done_at に現在時刻を入れて commit
                               ▼
                             models.py ⇄ SQLite
                               │
                               ▼
                             service.to_read()
                               │ ⑤ schemas.InstanceRead に変換、is_overdue を計算
                               ▼
画面 ◀──JSON {"id":5, "done_at":"...Z", ...}──
```

役割を分けている理由：

| 層 | 知っていること | 知らないこと |
|---|---|---|
| router | URL、ステータスコード | DB の操作 |
| service | DB の読み書き、業務のルール | HTTP（404 など） |
| models | テーブルの形 | API の形 |
| schemas | API の形 | テーブルの形 |

service が HTTP を知らないので、スケジューラーやゴミ出しの登録スクリプトからも同じ関数を呼べる。
実際に `scheduler.py` と `seed_gomi.py` は、API を通さずに service の関数を呼んでいる。

---

## 4. ファイルごとの解説

### 4.1 config.py：設定

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/kuroko.db"
```

- `pydantic-settings` は、クラスに書いた項目名と同じ名前の環境変数（大文字小文字は区別しない）を読む。
  `DATABASE_URL=...` を設定すれば、`settings.database_url` がその値になる
- 開発 PC では初期値のまま `backend/data/kuroko.db` を使い、サーバーでは `.env` に
  `DATABASE_URL=sqlite:////var/lib/kuroko/kuroko.db` と書く（要件定義書 7.4「データの置き場所」）
- `TZ = ZoneInfo("Asia/Tokyo")` はコードに直接書いている。サーバーの OS のタイムゾーンが
  UTC のままでも、日本時間で計算されるようにするため

### 4.2 db.py：DB の接続と、日時の扱い

#### Engine と Session

| 用語 | たとえ | このコードでは |
|---|---|---|
| Engine | DB への電話回線 | `engine = make_engine(...)`。アプリ全体で1つ |
| Session | 1回の通話（この間の変更をまとめて確定 or 取り消し） | API の呼び出しごとに1つ |
| commit | 変更を確定する | `session.commit()` |

#### SQLite の設定（PRAGMA）

接続するたびに3つの設定を流している。

| 設定 | 理由 |
|---|---|
| `journal_mode=WAL` | API での読み込みと、スケジューラーの書き込みが同時に起きても待たされにくくなる |
| `busy_timeout=5000` | 書き込みが重なったとき、すぐエラーにせず5秒まで待つ |
| `foreign_keys=ON` | SQLite は外部キーの制約が初期設定でオフ。オンにしないと `ondelete="SET NULL"` が効かない |

#### UTCDateTime：日時を UTC で保存する型

SQLite にはタイムゾーン付きの日時型がない。`2026-11-07 08:00` とだけ保存すると、
それが日本時間なのか UTC なのか、後から分からなくなる。

そこで SQLAlchemy の `TypeDecorator` で、保存と読み出しの間に変換をはさむ自作の型を作った。

```
Python                         DB
2026-11-07 08:00+09:00  ──保存──▶  2026-11-06 23:00（UTC に変換して、印を外す）
2026-11-06 23:00+00:00  ◀─読出──   2026-11-06 23:00（UTC の印を付け直す）
```

- タイムゾーンなしの日時を保存しようとすると、`ValueError` で止める。
  「うっかり日本時間のまま保存した」という不具合を、書いた瞬間に気づけるようにするため
- 画面に返すときは `...Z`（UTC）で返し、日本時間への変換は画面側（JavaScript）で行う

#### get_db と get_now：依存性注入

```python
def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
```

`yield` を使うと、「Session を渡す → API の処理が終わるのを待つ → with を抜けて閉じる」
という流れを1つの関数で書ける。FastAPI がこの関数を呼び、`yield` した値を API に渡す。

`get_now()` は `datetime.now(UTC)` を返すだけの関数だが、わざわざ分けている。
テストで `app.dependency_overrides[get_now] = lambda: clock.now` と差し替えると、
「2026-11-23 の朝」や「8:00 を過ぎた後」を自由に作れる。
関数の中で直接 `datetime.now()` を呼ぶと、こうした時刻のテストが書けない。

### 4.3 models.py：テーブル定義

SQLAlchemy 2.0 の書き方では、`Mapped[型]` で Python 側の型を、`mapped_column(...)` で DB 側の細かい設定を書く。

```python
due_time: Mapped[time | None]                       # NULL 可の TIME 列
title: Mapped[str] = mapped_column(String(100))     # NULL 不可、100文字まで
```

`| None` を付けるかどうかで、列が NULL を許すかどうかが自動で決まる。

#### 3つのテーブル

```
task_templates（ルール）            task_instances（各回）
┌────────────────────┐          ┌───────────────────────────┐
│ id: 1                │          │ id: 10  template_id: 1        │
│ title: もやすごみ       │ 1 ─── n │ scheduled_date: 2026-11-07   │
│ rrule: FREQ=WEEKLY;  │          │ due_at: 2026-11-06 23:00 UTC │
│        BYDAY=WE,SA   │          │ done_at: NULL（未完了）         │
│ dtstart: 2026-04-01  │          ├───────────────────────────┤
│ due_time: 08:00      │          │ id: 11  template_id: NULL     │ ← 単発タスク
│ skip_group: gomi ────┼──┐       │ title: 牛乳を買う               │
└────────────────────┘  │       └───────────────────────────┘
                          │
skip_dates（休止日）        │
┌──────────────────────┐  │
│ skip_group: gomi ◀─────┼──┘ グループ名で結びつく
│ 2026-12-31 〜 2027-01-03 │
└──────────────────────┘
```

| 設計 | 理由 |
|---|---|
| ルールと各回を分ける | 完了チェックは「11/7 の回」に付けたい。ルール1行だけでは、どの回が終わったか持てない |
| 単発タスクも `task_instances` に入れる | 一覧・完了・通知の処理を、定期と単発で同じにできる |
| 休止日はグループで結びつける | 11/23 に止まるのはゴミ出しだけで、洗濯は止まらない。テンプレートに `skip_group` を持たせ、同じグループの休止日だけ効かせる |
| 休止日は期間（開始〜終了）で持つ | 年末年始の 12/31〜1/3 を1行で書ける |

#### UniqueConstraint：二重に作らない安全装置

```python
UniqueConstraint("template_id", "scheduled_date")
```

「同じテンプレートの同じ日の回」は DB に1行しか入らない。
生成処理は、コードの側でも「すでにある日は作らない」と確かめているが、
万一スケジューラーが2つ動いてしまっても、DB が最後の砦として二重登録をはじく。

#### ondelete="SET NULL"

テンプレートを消すと、そのテンプレートから作った回の `template_id` が NULL になる（回そのものは残る）。
「先月ちゃんとゴミを出したか」という完了の履歴を、テンプレートを消しても失わないため。

### 4.4 recurrence.py：繰り返しの計算

#### RRULE とは

カレンダーの標準規格（RFC 5545）で決められた、繰り返しの書き方。
Google カレンダーや iPhone のカレンダーも、内部ではこの形式を使っている。

| 要件定義書 2.1 のパターン | RRULE |
|---|---|
| 毎日 | `FREQ=DAILY` |
| 毎週 月・木 | `FREQ=WEEKLY;BYDAY=MO,TH` |
| 第2・第4水曜 | `FREQ=MONTHLY;BYDAY=2WE,4WE` |
| 3日おき | `FREQ=DAILY;INTERVAL=3` |
| 毎月25日 | `FREQ=MONTHLY;BYMONTHDAY=25` |
| （参考）毎月の最終金曜 | `FREQ=MONTHLY;BYDAY=-1FR` |

自分で「第2水曜は何日か」を計算するコードを書くと、間違えやすく、テストも大変。
規格の形式で保存し、計算は python-dateutil の `rrulestr` に任せる。

```python
r = rrulestr("FREQ=WEEKLY;BYDAY=WE,SA", dtstart=datetime(2026, 4, 1))
r.between(datetime(2026, 11, 5), datetime(2026, 11, 19), inc=True)
# → 11/7, 11/11, 11/14, 11/18
```

- `dtstart`（起点日）は「3日おき」の数え始めに使う。11/2 起点なら 11/2, 5, 8, 11 …
- `inc=True` は「両端の日も含める」という意味

#### validate_rrule：入力のチェック

| はじくもの | 理由 |
|---|---|
| `FREQ=SECONDLY` など | 2週間分でも膨大な回ができてしまう |
| `DTSTART` を含むもの | 起点日は `dtstart` 列で持つ。2か所に書けると、どちらが正しいか分からない |
| 読めないもの | 保存してから生成のときにエラーになるより、登録の時点で 422 を返すほうが原因が分かりやすい |

#### DB を使わない関数にした理由

`occurrences()` は「ルールと日付を入れたら、日付のリストが返る」だけの関数（純粋関数）。
DB もサーバーも用意せずにテストできるので、[test_recurrence.py](../../backend/tests/test_recurrence.py) は
一瞬で終わる。要件定義書 7.6 の「繰り返しの計算は間違えやすいため、最初からテストを書く」をこの形で実現している。

### 4.5 schemas.py：API の入出力の形

#### models と schemas を分ける理由

| | models.py | schemas.py |
|---|---|---|
| ライブラリ | SQLAlchemy | Pydantic |
| 決めること | DB にどう保存するか | API で何を受け取り、何を返すか |
| 例 | `created_at` 列がある | `created_at` は返さない |
| 例 | `is_overdue` 列はない | `is_overdue` を計算して返す |

分けておくと、DB に列を足しても API の形は勝手に変わらない。

#### 入力のチェック

```python
title: str = Field(min_length=1, max_length=100)
due_at: AwareDatetime | None = None
```

- `Field(min_length=1)`：空文字のタイトルを 422 ではじく
- `AwareDatetime`：`2026-11-10T18:00:00+09:00` のようにタイムゾーン付きの日時だけを受け付ける。
  `2026-11-10T18:00:00` だけだと日本時間か UTC か分からないため（テスト `test_due_at_without_timezone_is_rejected`）
- `@field_validator`：1つの項目のチェック（RRULE が読めるか）
- `@model_validator(mode="after")`：項目どうしの関係のチェック（終了日が開始日より前でないか）

#### exclude_unset：「送らなかった」と「null を送った」の区別

`PATCH /api/task-templates/1` で次の2つは意味が違う。

| 送った JSON | 意味 |
|---|---|
| `{"title": "燃えるゴミ"}` | タイトルだけ変える。期限の時刻はそのまま |
| `{"due_time": null}` | 期限の時刻をなくす |

`data.model_dump(exclude_unset=True)` は「実際に送られてきた項目だけ」を返すので、この2つを区別できる。

#### 開発中に実際に起きた不具合：日時の形式のずれ

最初のテストで、次の失敗が出た。

```
assert '2026-11-10T00:30:00+09:00' == '2026-11-09T15:30:00Z'
```

同じ時刻なのに、表し方が違う。原因はこうだった。

1. 画面から `+09:00` 付きの日時を受け取る
2. DB には UTC で保存される（UTCDateTime の働き）
3. しかし Python のメモリ上のオブジェクトは `+09:00` のまま残っている
   （`expire_on_commit=False` なので、commit 後も DB から読み直さない）
4. それをそのまま返したので `+09:00` で返った。一覧の API は DB から読むので `Z` で返る

→ `InstanceRead` に「返す前に必ず UTC にそろえる」バリデーターを足して直した。
画面側から見て「同じ API なのに、呼び方によって形式が違う」のは不具合の元なので、返す側でそろえる。

### 4.6 service.py：処理の中身

#### 回の生成は「冪等」

冪等（べきとう）とは、何回実行しても結果が同じになること。

```python
existing = set(既にある日付)
for day in ルールに当てはまる日:
    if day in existing or 休止日:
        continue
    追加
```

生成は「起動時」「毎日 0:05」「テンプレートの登録・変更時」「休止日の削除時」と何度も呼ばれるが、
すでにある日は作らないので、何回呼んでも重複しない（テスト `test_generate_is_idempotent`）。

#### flush と commit の違い

```python
session.add(template)
session.flush()   # INSERT だけ実行して template.id を確定（まだ確定ではない）
generate_for_template(session, template, ...)   # template.id を使って回を作る
session.commit()  # ここで全部まとめて確定
```

`flush` は「SQL を DB に送るが、確定はしない」。途中でエラーになれば、テンプレートも回もまとめて取り消される。

#### テンプレートを変えたとき（要件定義書の未決 A-6 を採用）

| 回 | 扱い |
|---|---|
| 今日以降・未完了 | 消して、新しいルールで作り直す |
| 完了済み | 残す（履歴） |
| 過去・未完了（期限切れ） | 残す（期限切れとして出し続ける） |

#### 一覧（list_tasks）に出すもの

1. その日の回（完了済みも含む。チェックを付けた瞬間に消えると、押し間違いに気づけないため）
2. 期限切れの未完了の回（何日前のものでも。要件定義書 2.5「放置しにくい表示」）
3. 期限なしの単発タスクのうち、未完了のものと、その日に完了したもの

並び順は「期限切れ → 期限の早い順 → 期限なし」。

#### 期限切れの判定が2か所にある理由

`is_overdue()`（Python）と `_overdue_condition()`（SQL の条件）は同じ判定をしている。

- SQL 側：DB から「期限切れのものを取り出す」ために必要
- Python 側：取り出した1件ずつに `is_overdue: true/false` を付けるために必要

1か所にまとめる方法もあるが、今の規模では2か所に書いて、テストで両方を確かめるほうが分かりやすい。
判定を変えるときは、必ず両方を直すこと。

#### 定期タスクの回は削除できない（409）

消しても、次の生成で「この日の回がない」と判断されて作り直されてしまう。
「今週だけゴミ出しを休む」なら、完了にするか、休止日を登録する。

### 4.7 router.py：API の入口

```python
DB = Annotated[Session, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]

@router.patch("/task-instances/{instance_id}", response_model=InstanceRead)
def update_instance(instance_id: int, data: InstanceUpdate, db: DB, now: Now):
```

FastAPI は引数の書き方から、値をどこから取るかを判断する。

| 引数 | 取り出し元 |
|---|---|
| `instance_id: int` | URL の `{instance_id}`（数字でなければ 422） |
| `data: InstanceUpdate` | リクエストの JSON 本体 |
| `db: DB` | `get_db()` を呼んだ結果 |
| `day: ... Query(alias="date")` | URL の `?date=...` |

`response_model=InstanceRead` は「返す値をこの形に変換する」という指定。
`/docs` の API 仕様書にも反映され、Phase 1 の手順2では、ここから TypeScript の型を自動で作る（openapi-typescript）。

#### ステータスコード

| コード | 意味 | 使っている場面 |
|---|---|---|
| 200 | 成功 | 取得・変更 |
| 201 | 作成した | 追加 |
| 204 | 成功、返すものなし | 削除 |
| 404 | 見つからない | 存在しない id |
| 409 | 状態がぶつかる | 定期タスクの回を削除しようとした |
| 422 | 入力がおかしい | Pydantic のチェックに通らない（FastAPI が自動で返す） |

### 4.8 scheduler.py と main.py：起動とスケジューラー

#### lifespan：起動時と終了時の処理

```python
@asynccontextmanager
async def lifespan(app):
    run_generate()        # 起動時：止まっていた間の生成漏れを埋める
    scheduler.start()
    yield                 # ← ここでアプリが動いている
    scheduler.shutdown()  # 終了時
```

#### APScheduler の設定

| 設定 | 理由 |
|---|---|
| `AsyncIOScheduler(timezone=TZ)` | 「0:05」を日本時間として扱う |
| 普通の関数（`def`）を登録 | APScheduler が別スレッドで実行するので、DB の処理中も API の応答が止まらない |
| `misfire_grace_time=3600` | サーバーが止まっていて 0:05 を逃しても、1時間以内に起動すれば実行する |
| `coalesce=True` | 逃した回が複数あっても、まとめて1回だけ実行する |

#### uvicorn は必ず1プロセス（--workers 1）

プロセスを2つにすると、スケジューラーも2つ動く。今の生成処理は UniqueConstraint で守られているが、
手順4で作る通知の送信は二重に届いてしまう。

### 4.9 Alembic：DB の変更履歴

テーブルの形を変えたとき、サーバーの DB（データが入っている）を安全に作り替えるための仕組み。

```bash
# 1. models.py を変更する
# 2. 差分から変更履歴ファイルを自動で作る
uv run alembic revision --autogenerate -m "reminders テーブルを追加"
# 3. できたファイル（alembic/versions/xxxx.py）を目で確認する
# 4. DB に反映する
uv run alembic upgrade head
```

このプロジェクト用に変えた設定：

| ファイル | 変更 | 理由 |
|---|---|---|
| `alembic/env.py` | 接続先を `app.db.engine` にした | アプリと同じ DB を必ず使う（設定を2か所に書かない） |
| `alembic/env.py` | `render_as_batch=True` | SQLite は ALTER TABLE がほとんどできない。batch モードなら「新しい表を作ってコピーして入れ替える」方法で変更してくれる |
| `alembic/script.py.mako` | `import app.db` を追加 | 変更履歴ファイルの中で、自作の `UTCDateTime` 型を使うため |

> **テストでは Alembic を使っていない**：`Base.metadata.create_all()` で models.py からテーブルを直接作っている（速いため）。
> そのため「models.py を変えたのに変更履歴を作り忘れた」はテストでは見つからない。models.py を変えたら必ず `revision --autogenerate` すること。

### 4.10 テスト

#### fixture（conftest.py）

```python
@pytest.fixture
def client(session, clock):
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_now] = lambda: clock.now
    with TestClient(app) as c:
        yield c
```

- テスト関数の引数に `client` と書くと、pytest がこの関数を呼んで結果を渡す
- `session` fixture は、テストごとに一時フォルダに空の DB を作る。テストどうしが影響し合わない
- `dependency_overrides` で、本物の DB・時計をテスト用に差し替える（4.2 の get_db・get_now の出番）

#### テストの書き方の例

```python
def test_overdue_listed_first_and_counted(client, clock):
    clock.set(2026, 11, 7, 6, 0)           # 土曜 6:00（日本時間）
    client.post("/api/task-templates", json=MOYASU)
    clock.set(2026, 11, 7, 8, 30)          # 8:00 を過ぎた
    body = client.get("/api/tasks").json()
    assert body["overdue_count"] == 1      # もやすごみが期限切れ
```

時計を進めて「8:00 を過ぎた」状況を作れるのは、`get_now` を差し替えているから。

#### テストで確かめていること

| 分類 | 内容 |
|---|---|
| 繰り返し | 5パターン、起点日、休止日（11/23、年末年始） |
| 入力チェック | 不正な RRULE、タイムゾーンなしの日時 |
| 生成 | 2週間分、冪等、休止日のグループ、休止日の追加・削除 |
| 変更・削除 | テンプレート変更で作り直し（完了済みは残る）、削除で履歴が残る |
| 一覧 | 期限切れが先頭、件数、日本時間の「今日」、単発タスクの表示期間 |

### 4.11 seed_gomi.py：ゴミ出しの登録

```bash
uv run python -m app.tasks.seed_gomi
```

`python -m app.tasks.seed_gomi` は「`app/tasks/seed_gomi.py` をモジュールとして実行する」という意味。
ファイルを直接 `python app/tasks/seed_gomi.py` で実行すると、`from app.xxx import ...` が通らない。

- 休止日を先に登録している。テンプレートを登録した瞬間に回が作られるので、後から休止日を足すと一度作った回を消す処理が走ってしまうため（結果は同じだが無駄がない）
- 毎年4月、新しい収集日一覧表が出たら `SKIP_DATES` に書き足して再実行する

---

## 5. このステップで決めたこと

前回の「着手前に決めたいこと（A）」のうち、ここで採用したもの。

| No. | 内容 | 採用した形 |
|---|---|---|
| A-1 | 繰り返しルールの保存形式 | RRULE 文字列 ＋ 起点日 `dtstart` |
| A-2 | 休止日がどのタスクに効くか | `skip_group` で結びつける |
| A-3 | 日時の持ち方 | DB は UTC、計算と表示は日本時間 |
| A-6 | テンプレートを変更したとき | 今日以降の未完了の回だけ作り直す |

A-4（通知時刻）・A-5（送信済みの記録）・A-7（停止中の通知）は手順4（通知）で、A-8（画面の作り方）は手順2で扱う。

---

## 6. 試してみよう（任意）

理解を確かめたいときの練習。答えを見る前に、どこを触ればよいか考えてみると身につきやすい。

1. `/docs` から「毎月の最終金曜に家計簿の締め」という定期タスクを登録してみる（ヒント：4.4 の表）
2. `test_recurrence.py` に「第1月曜」のテストを足してみる
3. 期限切れタスクを、期限の古い順ではなく新しい順に並べたいときは、service.py のどこを変えるか
4. `task_templates` に「メモ」列を足すとき、変更が必要なファイルはどれか（答え：models.py、schemas.py、Alembic の変更履歴の3つ）

---

## 7. 次のステップ

Phase 1 の手順2「タスクの画面」：React + TypeScript で、今日のタスク一覧・完了チェック・単発タスクの追加の画面を作る。
