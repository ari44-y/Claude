import { describe, expect, it } from 'vitest'

import { addDays, formatDayLabel, formatTime, localInputToIso, todayJst, toJstDate } from './datetime'

describe('todayJst', () => {
  it('UTC ではまだ前日でも、日本時間の日付を返す', () => {
    // UTC 11/6 15:30 ＝ 日本時間 11/7 0:30
    expect(todayJst(new Date('2026-11-06T15:30:00Z'))).toBe('2026-11-07')
  })
})

describe('addDays', () => {
  it('月や年をまたいでも正しく足し引きできる', () => {
    expect(addDays('2026-11-30', 1)).toBe('2026-12-01')
    expect(addDays('2027-01-01', -1)).toBe('2026-12-31')
  })
})

describe('表示用の整形', () => {
  it('UTC の 23:00 は日本時間の翌日 8:00', () => {
    expect(formatTime('2026-11-06T23:00:00Z')).toBe('08:00')
    expect(toJstDate('2026-11-06T23:00:00Z')).toBe('2026-11-07')
  })

  it('日付の見出し', () => {
    expect(formatDayLabel('2026-11-07')).toBe('11/7(土)')
  })
})

describe('localInputToIso', () => {
  it('入力欄の値に日本時間の印を付ける', () => {
    expect(localInputToIso('2026-11-10T18:00')).toBe('2026-11-10T18:00:00+09:00')
  })
})
