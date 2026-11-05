import { useSearchParams } from 'react-router'

import { useDeleteTask, useTasks, useToggleDone } from '../api/tasks'
import { AddTaskForm } from '../components/AddTaskForm'
import { TaskItem } from '../components/TaskItem'
import { addDays, formatDayLabel, todayJst } from '../lib/datetime'

/** タスク画面：表示中の日のタスク一覧、日付の切り替え、単発タスクの追加。 */
export function TasksPage() {
  // 表示中の日付は URL（/tasks?date=2026-11-07）に持たせる。
  // state で持つより、ブラウザの「戻る」やリロードでも同じ日が表示されるので扱いやすい
  const [params, setParams] = useSearchParams()
  const today = todayJst()
  const day = params.get('date') ?? today
  const setDay = (d: string) => setParams(d === today ? {} : { date: d })

  const tasks = useTasks(day)
  const toggle = useToggleDone(day)
  const remove = useDeleteTask()

  return (
    <div className="space-y-4">
      {/* 日付の切り替え */}
      <div className="flex items-center justify-between">
        <DayButton onClick={() => setDay(addDays(day, -1))} label="前の日">
          ‹
        </DayButton>
        <div className="text-center">
          <div className="text-lg font-bold">{formatDayLabel(day)}</div>
          {day === today ? (
            <div className="text-xs text-brand">今日</div>
          ) : (
            <button type="button" onClick={() => setDay(today)} className="text-xs text-gray-500 underline">
              今日に戻る
            </button>
          )}
        </div>
        <DayButton onClick={() => setDay(addDays(day, 1))} label="次の日">
          ›
        </DayButton>
      </div>

      {/* 期限切れがあれば、目立つ帯を出す（要件定義書 2.5「アプリ内の表示」） */}
      {tasks.data && tasks.data.overdue_count > 0 && (
        <p className="rounded-xl bg-red-600 px-4 py-2 font-bold text-white">
          ⚠️ 期限切れが {tasks.data.overdue_count} 件あります
        </p>
      )}

      <AddTaskForm />

      {/* 読み込み中・エラー・空・一覧 の4つの状態を出し分ける */}
      {tasks.isPending ? (
        <p className="py-8 text-center text-gray-400">読み込み中…</p>
      ) : tasks.isError ? (
        <div className="py-8 text-center">
          <p className="text-red-600">読み込めませんでした：{tasks.error.message}</p>
          <button type="button" onClick={() => tasks.refetch()} className="mt-2 text-sm underline">
            もう一度読み込む
          </button>
        </div>
      ) : tasks.data.items.length === 0 ? (
        <p className="py-8 text-center text-gray-400">この日のタスクはありません 🎉</p>
      ) : (
        <ul className="space-y-2">
          {/* key：React が「どの行がどのタスクか」を見分けるための印。並び替わっても正しく描き直せる */}
          {tasks.data.items.map((task) => (
            <TaskItem
              key={task.id}
              task={task}
              day={day}
              onToggle={(done) => toggle.mutate({ id: task.id, done })}
              onDelete={
                task.template_id === null
                  ? () => {
                      if (confirm(`「${task.title}」を削除しますか？`)) remove.mutate(task.id)
                    }
                  : undefined
              }
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function DayButton({ onClick, label, children }: { onClick: () => void; label: string; children: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="flex size-11 items-center justify-center rounded-full text-2xl text-gray-500 active:bg-gray-200"
    >
      {children}
    </button>
  )
}
