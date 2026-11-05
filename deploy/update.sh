#!/usr/bin/env bash
# サーバー（Ubuntu Server）で実行する更新スクリプト。
#   Mac で git push → サーバーで ./deploy/update.sh
#
# 1. GitHub から最新を取ってくる
# 2. イメージを作り直して、コンテナを入れ替える（DB の作り替えはコンテナの起動時に自動）
# 3. 使わなくなった古いイメージを消す（ノートパソコンのストレージを圧迫しないように）

# -e：途中でエラーが起きたら止まる  -u：未定義の変数を使ったら止まる
# -o pipefail：パイプ（|）の途中のエラーも見逃さない
set -euo pipefail

# どこから実行しても、リポジトリのフォルダで動くようにする
cd "$(dirname "$0")/.."

# --ff-only：サーバー側で誤ってファイルを変えていたら、勝手にマージせずに止まる
git pull --ff-only

docker compose -f compose.prod.yaml up -d --build
docker image prune -f

docker compose -f compose.prod.yaml ps
