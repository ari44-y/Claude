/**
 * 日時の小道具。
 *
 * サーバーは日時を UTC（例："2026-11-06T23:00:00Z"）で返す。
 * 画面ではすべて日本時間で表示する。iPhone の設定に関係なく日本時間にするため、
 * ブラウザのタイムゾーンには頼らず、Asia/Tokyo を毎回指定する。
 */

const TZ = 'Asia/Tokyo'

// Intl.DateTimeFormat：ブラウザに最初からある、日時を地域の書き方に整える仕組み。
// 作るのに少し時間がかかるので、使い回せるように1回だけ作っておく
const dateFmt = new Intl.DateTimeFormat('en-CA', {
  // en-CA（カナダ英語）は日付を「2026-11-05」の形で出すので、YYYY-MM-DD を作るのに便利
  timeZone: TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})
const timeFmt = new Intl.DateTimeFormat('ja-JP', {
  timeZone: TZ,
  hour: '2-digit',
  minute: '2-digit',
})
const labelFmt = new Intl.DateTimeFormat('ja-JP', {
  timeZone: TZ,
  month: 'numeric',
  day: 'numeric',
  weekday: 'short',
})

/** 日本時間の今日の日付（"2026-11-05"）。 */
export function todayJst(now: Date = new Date()): string {
  return dateFmt.format(now)
}

/** "2026-11-05" の n 日後（n が負なら前）の日付。 */
export function addDays(day: string, n: number): string {
  // 正午（12:00 +09:00）にしておけば、足し引きしても日付の境目をまたぐ心配がない
  const d = new Date(`${day}T12:00:00+09:00`)
  d.setUTCDate(d.getUTCDate() + n)
  return dateFmt.format(d)
}

/** "2026-11-05" → "11/5(木)"（ja-JP で月・日を numeric にすると、この短い形になる） */
export function formatDayLabel(day: string): string {
  return labelFmt.format(new Date(`${day}T12:00:00+09:00`))
}

/** UTC の日時 → 日本時間の "08:00" */
export function formatTime(iso: string): string {
  return timeFmt.format(new Date(iso))
}

/** UTC の日時 → 日本時間の日付 "2026-11-05" */
export function toJstDate(iso: string): string {
  return dateFmt.format(new Date(iso))
}

/**
 * 日時の入力欄（<input type="datetime-local">）の値 → サーバーに送る形。
 * "2026-11-10T18:00" → "2026-11-10T18:00:00+09:00"
 *
 * 入力欄の値にはタイムゾーンが付いていない。日本時間として扱うことを、+09:00 を付けて明示する
 * （サーバーはタイムゾーンなしの日時を 422 で拒否する）。
 */
export function localInputToIso(value: string): string {
  return `${value}:00+09:00`
}
