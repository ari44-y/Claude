#!/usr/bin/env bash
# DB（とレシート画像）のバックアップ。サーバー本体の systemd タイマーから毎日実行する。
#   手動で試す：sudo ./deploy/backup.sh
#
# 設定は /etc/default/kuroko-backup（なくてもよい）で変えられる：
#   KUROKO_DATA_DIR=/var/lib/kuroko          バックアップ元（compose.prod.yaml の /data と同じ場所）
#   KUROKO_BACKUP_DIR=/mnt/usb/kuroko-backup  保存先（外付けストレージなど、本体とは別の場所が望ましい）
#   KUROKO_BACKUP_KEEP_DAYS=14               何日分残すか

set -euo pipefail

DATA_DIR="${KUROKO_DATA_DIR:-/var/lib/kuroko}"
BACKUP_DIR="${KUROKO_BACKUP_DIR:-/var/backups/kuroko}"
KEEP_DAYS="${KUROKO_BACKUP_KEEP_DAYS:-14}"

STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$BACKUP_DIR/$STAMP"
mkdir -p "$DEST"

# DB は cp でコピーしない。アプリが書き込んでいる最中にコピーすると、壊れたファイルになることがある。
# sqlite3 の .backup は、書き込みと重ならないように一貫した状態を写し取ってくれる。
# .timeout 5000：アプリが書き込み中なら、最大5秒待つ
sqlite3 -cmd ".timeout 5000" "$DATA_DIR/kuroko.db" ".backup '$DEST/kuroko.db'"

# アプリの DB は WAL 方式なので、コピーも WAL 方式になり、開くたびに -wal・-shm という付属ファイルができる。
# バックアップは1ファイルで完結していたほうが扱いやすいので、普通の方式（DELETE）に戻しておく
sqlite3 "$DEST/kuroko.db" "PRAGMA journal_mode=DELETE;" > /dev/null
# 方式を戻した後の付属ファイルは使われないので消す（環境によっては自動で消えずに残るため）
rm -f "$DEST/kuroko.db-wal" "$DEST/kuroko.db-shm"

# 取ったバックアップが壊れていないか確かめる（壊れていたら、ここでエラーになって止まる）
if [ "$(sqlite3 "$DEST/kuroko.db" 'PRAGMA integrity_check;')" != "ok" ]; then
  echo "バックアップした DB が壊れています: $DEST" >&2
  exit 1
fi

# レシート画像（Phase 3 で /data/receipts に置く予定）
if [ -d "$DATA_DIR/receipts" ]; then
  cp -a "$DATA_DIR/receipts" "$DEST/"
fi

# 古いバックアップを消す（日付の名前のフォルダだけを対象にする）
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +"$KEEP_DAYS" -exec rm -rf {} +

echo "バックアップしました: $DEST"
