# 解説 03：Docker での開発と本番

開発（Mac）も本番（Ubuntu Server）も Docker で動かす構成にした。その解説。

```
Mac で開発 ──git push──▶ GitHub ──git pull──▶ Ubuntu Server で docker compose up
```

---

## 1. このステップで作ったもの

| ファイル | 役割 |
|---|---|
| [compose.yaml](../../compose.yaml) | 開発用。API と画面の開発サーバーを2つのコンテナで動かす |
| [Dockerfile](../../Dockerfile) | 本番用のイメージの作り方（画面のビルド → API） |
| [compose.prod.yaml](../../compose.prod.yaml) | 本番用。Dockerfile からイメージを作って動かす |
| [.dockerignore](../../.dockerignore) | イメージ作りに渡さないファイル |
| [deploy/update.sh](../../deploy/update.sh) | サーバーで実行する更新スクリプト |

コードの変更は2か所だけ。

| ファイル | 変更 |
|---|---|
| [frontend/vite.config.ts](../../frontend/vite.config.ts) | API の中継先を環境変数 `API_ORIGIN` で変えられるようにした |
| [frontend/package.json](../../frontend/package.json) の `gen:api` | API 仕様を、起動中の API（`/openapi.json`）から取るようにした。画面のコンテナには Python がないため |

---

## 2. Docker の用語

| 用語 | たとえ | このプロジェクトでは |
|---|---|---|
| イメージ | アプリを入れた箱の設計図＋中身（読み取り専用） | `node:26-slim`、`kuroko-app` など |
| コンテナ | イメージから作った、動いている箱 | `kuroko-dev-backend-1` など |
| Dockerfile | イメージの作り方を書いた手順書 | 本番用の [Dockerfile](../../Dockerfile) |
| Compose | 複数のコンテナの起動方法をまとめて書くもの | `compose.yaml`、`compose.prod.yaml` |
| ボリューム | コンテナを消しても残る保存場所 | DB、`node_modules`、`.venv` |
| バインドマウント | Mac（本体）のフォルダを、そのままコンテナに見せる | 開発中のソースコード |
| ポートの公開 | 本体のポートとコンテナのポートをつなぐ | `8000:8000`、`5173:5173` |

コンテナは「使い捨て」が前提。作り直すと中身は消える。消えて困るもの（DB）は、必ずボリュームかバインドマウントに置く。

---

## 3. 開発（Mac・Windows 共通）

### 3.1 使い方

リポジトリのフォルダ（`Claude/`）で実行する。

```bash
docker compose up          # 起動（ログが流れ続ける。Ctrl+C で停止）
docker compose up -d       # 裏で起動（-d：detached）
docker compose logs -f backend   # API のログを見る
docker compose down        # 停止してコンテナを消す（DB などのボリュームは残る）
docker compose down -v     # ボリュームも消す（開発用 DB を空からやり直したいとき）
```

起動したら：

- 画面：http://localhost:5173
- API の画面：http://localhost:8000/docs

コンテナの中でコマンドを実行するときは `docker compose exec <サービス名> <コマンド>`。

| やりたいこと | コマンド |
|---|---|
| バックエンドのテスト | `docker compose exec backend uv run pytest` |
| ゴミ出しの登録 | `docker compose exec backend uv run python -m app.tasks.seed_gomi` |
| DB の変更履歴を作る | `docker compose exec backend uv run alembic revision --autogenerate -m "説明"` |
| ライブラリを足す（Python） | `docker compose exec backend uv add <名前>` |
| 画面のテスト | `docker compose exec frontend npm test` |
| API の型を作り直す | `docker compose exec frontend npm run gen:api` |
| ライブラリを足す（画面） | `docker compose exec frontend npm install <名前>` |

`uv add` や `alembic revision` で作られたファイル（`pyproject.toml`、`alembic/versions/...`）は、バインドマウントで Mac のフォルダに直接書かれるので、そのまま Git にコミットできる。

### 3.2 compose.yaml の中身

```
Mac のブラウザ
  │ localhost:5173            │ localhost:8000
  ▼                           ▼
┌─ frontend コンテナ ─┐     ┌─ backend コンテナ ─┐
│ node:26-slim       │     │ uv + Python 3.12  │
│ npm run dev        │──▶──│ uvicorn --reload  │
│ /api を中継         │ http://backend:8000    │
└────────────────┘     └───────────────┘
  ↑ ./frontend をマウント        ↑ ./backend をマウント
  ↑ node_modules はボリューム     ↑ /venv（.venv）・/data（DB）はボリューム
```

ポイント：

**① 公式イメージをそのまま使う**
開発用には Dockerfile を書かず、`node:26-slim` と uv の公式イメージをそのまま使っている。
必要なライブラリは、起動のたびに `uv sync` と `npm install` で入れる（入っていれば数秒で終わる）。

**② ソースコードはバインドマウント**
`./backend:/app/backend` は「Mac の backend フォルダを、コンテナの /app/backend として見せる」という意味。
Mac のエディタで保存すると、コンテナの中の uvicorn（`--reload`）や Vite（HMR）がすぐに気づいて読み直す。

**③ node_modules と .venv は Mac と共有しない**

```yaml
- ./frontend:/app/frontend
- frontend-node-modules:/app/frontend/node_modules   # ← ここだけボリュームで上書き
```

`node_modules` の中には、Vite（rolldown）や oxlint の実行ファイルが入っている。これは Mac 用と Linux 用で別物。
Mac の `node_modules` をコンテナで使うと「実行ファイルの形式が違う」というエラーになる。
そこで `node_modules` の場所だけ、コンテナ専用のボリュームで覆い隠している。
Python も同じ理由で、`UV_PROJECT_ENVIRONMENT=/venv` にして `.venv` をコンテナ専用のボリュームに作っている。

> **Mac にある `frontend/node_modules` と `backend/.venv` について**：コンテナでは使わないが、
> VS Code の補完や型チェックのために残しておいてよい。ライブラリを足したときは、Mac 側でも
> `npm install`・`uv sync` しておくと、エディタの補完が最新になる。

**④ コンテナどうしはサービス名で呼び合う**
frontend コンテナから見た `localhost` は、frontend コンテナ自身のこと。backend の API には届かない。
Compose は、同じファイルのサービスどうしを名前（`backend`）で呼べるようにしてくれるので、中継先を `http://backend:8000` にしている。

**⑤ `--host 0.0.0.0`**
Vite も uvicorn も、初期設定では「同じ機械（コンテナの中）からの接続」しか受け付けない。
`0.0.0.0` にすると、コンテナの外（Mac のブラウザ）からの接続も受け付ける。

---

## 4. 本番（Ubuntu Server）

### 4.1 Dockerfile：2段階のイメージ作り（マルチステージビルド）

```
1段目 frontend（node:26-slim）           2段目 app（uv + Python）
┌────────────────────────┐       ┌───────────────────────────┐
│ npm ci                  │       │ uv sync --no-dev           │
│ npm run build           │       │ backend のコード             │
│  → /app/frontend/dist ──┼─コピー─▶│ /app/frontend/dist         │
│ （node_modules 数百MB）   │       │ alembic → uvicorn で起動      │
└────────────────────────┘       └───────────────────────────┘
       ↑ 最終的なイメージには入らない            ↑ これが kuroko-app（約330MB）
```

画面のビルドには Node が必要だが、動かすときは不要（ビルド結果は HTML・JS・CSS のファイルだけ）。
1段目でビルドし、結果の `dist` だけを2段目にコピーすることで、Node や `node_modules` を本番のイメージに入れずに済む。

#### キャッシュを効かせる順番

```dockerfile
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci                 # ← package.json が変わらなければ、前回の結果を再利用
COPY frontend/ ./
RUN npm run build
```

Docker は手順（行）ごとに結果を保存し、入力が同じなら再利用する。
ライブラリの一覧だけを先にコピーしてインストールしておくと、ソースコードだけを直したときは時間のかかる `npm ci` が飛ばされる。
Python の `uv sync` も同じ考え方で2回に分けている。

#### 起動コマンド

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
```

- 起動のたびに `alembic upgrade head` で DB を最新の形にする。テーブルの変更を含む更新でも、`update.sh` を実行するだけで済む
- `exec`：uvicorn を、シェルの子ではなくコンテナの本体のプロセスにする。`docker stop` の停止の合図が uvicorn に直接届き、スケジューラーなどをきちんと止めてから終了できる
- `--workers 1`：スケジューラーが二重に動かないよう、必ず1プロセス

### 4.2 compose.prod.yaml

| 設定 | 理由 |
|---|---|
| `restart: unless-stopped` | サーバーが再起動しても自動で起動する（systemd のサービスの代わり）。自分で止めたときだけは止まったまま |
| `ports: "127.0.0.1:8000:8000"` | サーバー本体からしか接続できないようにする（下の注意） |
| `/var/lib/kuroko:/data` | DB をサーバー本体のフォルダに置く。コンテナを作り直しても消えず、本体のバックアップからも読める |
| `env_file: .env`（なくてもよい） | VAPID 鍵などの秘密の値を渡す。`.env` は Git に入れない |
| `healthcheck` | 30秒ごとに `/api/health` を呼ぶ。応答がなければ `docker ps` に unhealthy と出る |

> **注意：Docker と ufw（ファイアウォール）**
> Docker が公開したポートは、Ubuntu のファイアウォール（ufw）の設定を素通りする。
> `"8000:8000"` と書くと、ufw で 8000 番を閉じていても、家の LAN の他の機器から直接開けてしまう。
> `127.0.0.1:` を付けて「サーバー本体からだけ」にし、外からの入口は Tailscale だけにする。

### 4.3 Tailscale はサーバー本体に入れる

```
iPhone ──(Tailscale・HTTPS)──▶ サーバー本体の Tailscale
                                  │ tailscale serve --bg 8000
                                  ▼
                               127.0.0.1:8000 ──▶ コンテナ kuroko-app
```

Tailscale をコンテナに入れる方法もあるが、設定が複雑になる。本体に入れれば、ssh での接続（`update.sh` の実行）にもそのまま使える。

### 4.4 更新の流れ（deploy/update.sh）

```bash
git pull --ff-only
docker compose -f compose.prod.yaml up -d --build
docker image prune -f
```

| 部分 | 意味 |
|---|---|
| `set -euo pipefail` | 途中でエラーが起きたら、そこで止める（壊れたまま次に進まない） |
| `--ff-only` | サーバー側でファイルを変えてしまっていたら、勝手にマージせずに止まる |
| `up -d --build` | イメージを作り直し、変わっていればコンテナを入れ替える |
| `image prune -f` | 入れ替えで使われなくなった古いイメージを消す（ノートパソコンのストレージを圧迫しないように） |

> **イメージはサーバーで作る**：Mac（Apple シリコン）は arm64、サーバーのノートパソコンは多くの場合 x86_64 で、CPU の種類が違う。
> Mac で作ったイメージはそのままでは動かないので、GitHub からソースコードを持っていき、サーバーで作る。

---

## 5. Windows で開発するとき

コンテナの中は、Mac でも Windows でも同じ Linux なので、Python・Node のバージョンやライブラリの違いは気にしなくてよい。
ただし、コンテナに渡す前の部分（Git がファイルを取り出す処理、Windows 上のフォルダ）には OS の差が残る。

### 5.1 改行コード（.gitattributes で対策済み）

Git for Windows は初期設定で、取り出すときに改行を CRLF（Windows 形式）に変える。
CRLF のシェルスクリプトを Linux で実行すると、行末の `\r` まで命令の一部とみなされて動かない。

```
/usr/bin/env: 'bash\r': No such file or directory
```

[.gitattributes](../../.gitattributes) に `* text=auto eol=lf` と書き、どの PC でも LF で取り出すようにしている。
PC ごとの Git の設定（`core.autocrlf`）に頼らないので、設定し忘れても安全。

### 5.2 リポジトリは WSL2 の中に置く

Windows の Docker Desktop は、内部で WSL2（Windows の中で動く Linux）を使っている。
リポジトリを `C:\Users\...` に置くと、Windows と Linux の境目をまたいでファイルを読むことになり、次の問題が起きやすい。

| 問題 | 内容 |
|---|---|
| 自動で読み直されない | 保存しても変更の通知がコンテナに届かず、uvicorn の `--reload` や Vite の自動更新が動かない |
| 遅い | `npm install` や画面の表示に時間がかかる |

WSL2 の中に clone すれば、Mac と同じように動く。

```bash
# WSL2 の Ubuntu のターミナルで
cd ~
git clone https://github.com/ari44-y/Claude.git
cd Claude
code .            # VS Code が「WSL」拡張で開く
docker compose up
```

Windows のエクスプローラーからは `\\wsl$\Ubuntu\home\<ユーザー名>\Claude` で見られる。

> **どうしても `C:\` に置きたい場合**：変更の通知を待たず、一定間隔でファイルを見に行く（ポーリング）設定にする。
> compose.yaml の backend の `environment` に `WATCHFILES_FORCE_POLLING: "true"`、frontend に `CHOKIDAR_USEPOLLING: "true"` を足し、
> vite.config.ts の `server` に `watch: { usePolling: true }` を足す。CPU を少し多く使う。

### 5.3 PC ごとに別になるもの

| もの | 扱い |
|---|---|
| 開発用の DB（Docker のボリューム） | Mac と Windows で共有しない。それぞれで `docker compose exec backend uv run python -m app.tasks.seed_gomi` を1回実行すれば、ゴミ出しの登録はそろう |
| エディタの補完用の `node_modules`・`.venv` | OS ごとに中身が違う。Git には入らないので、それぞれの PC で `npm install`（frontend）・`uv sync`（backend）を1回実行する |

---

## 6. Mac で本番用のイメージを試す

サーバーに持っていく前に、Mac で本番と同じ形を試せる。DB の置き場所を一時フォルダに変えて起動する。

```bash
mkdir -p /tmp/kuroko-data
KUROKO_DATA_DIR=/tmp/kuroko-data docker compose -f compose.prod.yaml up -d --build
# → http://localhost:8000
KUROKO_DATA_DIR=/tmp/kuroko-data docker compose -f compose.prod.yaml down
```

開発用（`compose.yaml`）と同じ 8000 番を使うので、先に `docker compose down` で開発用を止めておく。

---

## 7. このステップで決めたこと

| 内容 | 決定 |
|---|---|
| 開発環境 | Docker Compose（公式イメージ ＋ ソースコードのバインドマウント） |
| 本番環境 | Dockerfile（マルチステージビルド）＋ compose.prod.yaml |
| 反映の流れ | Mac → GitHub → サーバーで `deploy/update.sh` |
| Tailscale | サーバー本体に入れる |
| Claude Code（Phase 2） | API のコンテナの中に入れる。`kuroko/` は読み取り専用でマウント |
| バックアップ | サーバー本体の systemd タイマー |
| DB の作り替え | コンテナの起動時に自動 |
| 開発 PC | Mac と Windows。改行は `.gitattributes` で LF に統一、Windows は WSL2 の中に clone |

---

## 8. 試してみよう（任意）

1. `docker compose up -d` の後、`docker compose ps` でコンテナの状態を見る
2. `docker compose exec backend bash` でコンテナの中に入り、`ls /app/backend` や `ls /venv` を見てみる（`exit` で出る）
3. `backend/app/main.py` の `/api/health` の返り値を変えて保存し、`docker compose logs backend` で自動の再起動を確かめる
4. 6 の手順で本番用イメージを作り、`docker images kuroko-app` でイメージの大きさを見る

---

## 9. 次のステップ

Phase 1 の手順3の残り：Ubuntu Server の準備（Docker・Tailscale のインストール、ふたを閉じてもスリープしない設定、リポジトリの clone、`/var/lib/kuroko` の作成、バックアップのタイマー）。
