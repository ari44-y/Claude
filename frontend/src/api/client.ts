/**
 * サーバーとの通信の土台。
 *
 * schema.d.ts は `npm run gen:api` で FastAPI の API 仕様から自動で作ったファイル（手で直さない）。
 * openapi-fetch にその型を渡すと、URL・送る値・返る値に型が付く。
 *   api.GET('/api/taks')                       → URL の打ち間違いが型エラーになる
 *   api.POST('/api/tasks', { body: { titl } })  → 項目名の間違いが型エラーになる
 * サーバー側の schemas.py を変えたら、gen:api を実行し直すと、画面側の食い違いが型エラーとして見つかる。
 */
import createClient from 'openapi-fetch'

import type { components, paths } from './schema'

// baseUrl を空にすると、画面と同じサーバー（同じオリジン）の /api/... を呼ぶ。
// 開発時は Vite が FastAPI に中継する（vite.config.ts の proxy）
export const api = createClient<paths>({ baseUrl: '' })

// よく使う型に短い名前を付けておく
export type Task = components['schemas']['InstanceRead']
export type TaskList = components['schemas']['TaskList']

/** サーバーがエラーを返したときに投げる例外。 */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/**
 * openapi-fetch の戻り値 { data, error, response } から、
 * 成功なら data を取り出し、失敗なら ApiError を投げる。
 *
 * TanStack Query は「例外が投げられたら失敗」と判断するので、失敗を例外に変えておく必要がある。
 */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    throw new ApiError(result.response.status, errorMessage(result.error))
  }
  return result.data as T
}

/** FastAPI のエラーの形（{"detail": "..."} や、422 の {"detail": [{msg: ...}]}）から文言を取り出す。 */
function errorMessage(error: unknown): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) return String(detail[0]?.msg ?? '入力に誤りがあります')
  return '通信に失敗しました'
}
