# 本番用のイメージ（compose.prod.yaml から使う）。
#
# 2段階に分けて作る（マルチステージビルド）：
#   1段目 frontend：Node で React をビルドし、frontend/dist を作る
#   2段目 app    ：Python だけの軽いイメージに、バックエンドと 1段目の dist だけをコピーする
# Node や node_modules は 2段目に入らないので、イメージが小さく済む。

# ---------- 1段目：画面のビルド ----------
FROM node:26-slim AS frontend
WORKDIR /app/frontend

# 先に package.json だけをコピーして npm ci する。
# Docker は手順ごとに結果を保存（キャッシュ）しており、コピーしたファイルが変わらなければ再利用する。
# ソースコードだけを直したときは、時間のかかる npm ci が飛ばされる
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ---------- 2段目：実行用 ----------
# uv の公式イメージ（Debian + Python 3.12 + uv）
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS app

# UV_COMPILE_BYTECODE：起動を速くするため、インストール時に .pyc を作っておく
# UV_LINK_MODE=copy：キャッシュからのリンクではなくコピーで入れる（Docker の中ではこちらが確実）
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app/backend

# 1段目と同じ考え方：ライブラリの一覧だけ先にコピーして、ライブラリだけ入れる
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/ ./
RUN uv sync --locked --no-dev

# 1段目で作った画面のファイルだけを持ってくる
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# .venv の中のコマンド（uvicorn、alembic）を、そのまま名前で呼べるようにする
ENV PATH="/app/backend/.venv/bin:$PATH" \
    DATABASE_URL="sqlite:////data/kuroko.db" \
    FRONTEND_DIST="/app/frontend/dist"

EXPOSE 8000

# 起動するたびに DB を最新の形に作り替えてから（alembic upgrade head）、API を起動する。
# exec：uvicorn をシェルの子ではなく本体のプロセスにする。
#       docker stop の停止の合図が uvicorn に直接届き、きれいに終了できる
# --workers 1：スケジューラーが二重に動かないよう、必ず1プロセス（要件定義書 7.4）
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
