/**
 * タスクの取得・更新（TanStack Query のフック）。
 *
 * TanStack Query は、サーバーのデータを画面用にキャッシュ（一時保存）する仕組み。
 * - useQuery：取得。読み込み中・エラー・再取得（アプリに戻ってきたときなど）を任せられる
 * - useMutation：更新。終わったら関係するキャッシュを「古い」と印を付けて、取り直させる
 *
 * キャッシュは queryKey（["tasks", "2026-11-05"] のような配列）で区別する。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap, type Task, type TaskList } from './client'

export const taskKeys = {
  all: ['tasks'] as const,
  list: (day: string) => ['tasks', day] as const,
}

/** その日のタスク一覧。 */
export function useTasks(day: string) {
  return useQuery({
    queryKey: taskKeys.list(day),
    queryFn: async () => unwrap(await api.GET('/api/tasks', { params: { query: { date: day } } })),
  })
}

/** 単発タスクの追加。 */
export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { title: string; due_at: string | null }) =>
      unwrap(await api.POST('/api/tasks', { body })),
    // 成功したら、どの日の一覧も取り直す（期限によって出る日が変わるため、日付を絞らない）
    onSuccess: () => qc.invalidateQueries({ queryKey: taskKeys.all }),
  })
}

/**
 * 完了チェックの切り替え。
 *
 * 「楽観的更新」をしている：サーバーの返事を待たずに、先に画面のチェックを切り替える。
 * 外出先の遅い回線でも、タップした瞬間に反応するようにするため。失敗したら元に戻す。
 */
export function useToggleDone(day: string) {
  const qc = useQueryClient()
  const key = taskKeys.list(day)

  return useMutation({
    mutationFn: async ({ id, done }: { id: number; done: boolean }) =>
      unwrap(
        await api.PATCH('/api/task-instances/{instance_id}', {
          params: { path: { instance_id: id } },
          body: { done },
        }),
      ),

    // ① 送信の直前：画面のキャッシュを先に書き換える
    onMutate: async ({ id, done }) => {
      // 取得中の一覧が後から届いて、書き換えを上書きしないように止める
      await qc.cancelQueries({ queryKey: key })
      const previous = qc.getQueryData<TaskList>(key)
      if (previous) {
        qc.setQueryData<TaskList>(key, {
          ...previous,
          items: previous.items.map((t): Task =>
            t.id === id
              ? {
                  ...t,
                  done_at: done ? new Date().toISOString() : null,
                  is_overdue: done ? false : t.is_overdue,
                }
              : t,
          ),
        })
      }
      return { previous } // ② の onError に渡される
    },

    // ② 失敗したら、書き換える前の状態に戻す
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(key, context.previous)
    },

    // ③ 成功・失敗どちらでも、最後にサーバーの正しい状態を取り直す
    //    （期限切れの件数など、画面では計算していない値もそろえるため）
    onSettled: () => qc.invalidateQueries({ queryKey: taskKeys.all }),
  })
}

/** 単発タスクの削除。 */
export function useDeleteTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await api.DELETE('/api/task-instances/{instance_id}', {
          params: { path: { instance_id: id } },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: taskKeys.all }),
  })
}
