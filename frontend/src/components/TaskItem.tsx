import type { Task } from '../api/client'
import { formatDayLabel, formatTime, toJstDate } from '../lib/datetime'

type Props = {
  task: Task
  day: string // 表示中の日付。期限が別の日なら、日付も添えて表示する
  onToggle: (done: boolean) => void
  onDelete?: () => void // 単発タスクだけ渡される（定期タスクの回は削除できない）
}

/** タスク1行。期限切れは赤く、完了したら取り消し線にする。 */
export function TaskItem({ task, day, onToggle, onDelete }: Props) {
  const done = task.done_at !== null
  const overdue = task.is_overdue

  // 状態ごとに付けるクラスを変える。テンプレート文字列で、共通部分と状態別の部分をつなげる
  const box = overdue
    ? 'border-red-300 bg-red-50'
    : done
      ? 'border-gray-200 bg-gray-100'
      : 'border-gray-200 bg-white'

  return (
    <li className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${box}`}>
      {/*
        label で囲むと、チェックボックスだけでなく文字をタップしてもチェックが切り替わる。
        スマホでは小さいチェックボックスを狙って押すのが大変なので、押せる範囲を広げる
      */}
      <label className="flex min-h-8 flex-1 items-center gap-3">
        <input
          type="checkbox"
          checked={done}
          onChange={(e) => onToggle(e.target.checked)}
          // accent-*：ブラウザ標準のチェックボックスの色を変える。size-5：幅と高さを 1.25rem に
          className={`size-5 shrink-0 ${overdue ? 'accent-red-600' : 'accent-brand'}`}
        />
        <span className="flex-1">
          <span className={`block ${done ? 'text-gray-400 line-through' : ''} ${overdue ? 'font-bold text-red-700' : ''}`}>
            {task.title}
          </span>
          <Meta task={task} day={day} />
        </span>
      </label>

      {onDelete && (
        <button
          type="button"
          onClick={onDelete}
          className="-mr-2 p-2 text-gray-400 active:text-red-600"
          aria-label={`${task.title} を削除`}
        >
          ✕
        </button>
      )}
    </li>
  )
}

/** タイトルの下の小さい文字：期限・定期かどうか・期限切れ。 */
function Meta({ task, day }: { task: Task; day: string }) {
  const parts: string[] = []

  if (task.due_at) {
    // 表示中の日と期限の日が違う（前の日からの期限切れなど）なら、日付も出す
    const dueDay = toJstDate(task.due_at)
    const prefix = dueDay === day ? '' : `${formatDayLabel(dueDay)} `
    parts.push(`${prefix}${formatTime(task.due_at)} まで`)
  } else if (task.scheduled_date && task.scheduled_date !== day) {
    parts.push(formatDayLabel(task.scheduled_date))
  }
  if (task.template_id !== null) parts.push('定期')

  if (parts.length === 0 && !task.is_overdue) return null

  return (
    <span className={`block text-xs ${task.is_overdue ? 'text-red-600' : 'text-gray-500'}`}>
      {task.is_overdue && '⚠️ 期限切れ　'}
      {parts.join('・')}
    </span>
  )
}
