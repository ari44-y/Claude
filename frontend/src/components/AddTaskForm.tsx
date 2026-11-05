import { useState, type FormEvent } from 'react'

import { useCreateTask } from '../api/tasks'
import { localInputToIso } from '../lib/datetime'

/** 単発タスクの追加フォーム。期限は任意。 */
export function AddTaskForm() {
  // useState：この部品だけが覚えておく値。値が変わると、この部品が描き直される
  const [title, setTitle] = useState('')
  const [withDue, setWithDue] = useState(false)
  const [due, setDue] = useState('') // datetime-local の値（"2026-11-10T18:00"）

  const create = useCreateTask()

  function handleSubmit(e: FormEvent) {
    e.preventDefault() // フォームの送信でページが再読み込みされるのを止める
    const trimmed = title.trim()
    if (!trimmed) return

    create.mutate(
      { title: trimmed, due_at: withDue && due ? localInputToIso(due) : null },
      {
        // 成功したときだけ入力欄を空にする（失敗したら、打った文字を残して再送できるように）
        onSuccess: () => {
          setTitle('')
          setDue('')
          setWithDue(false)
        },
      },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2 rounded-xl border border-gray-200 bg-white p-3">
      <div className="flex gap-2">
        {/*
          制御されたコンポーネント：入力欄の値を state で持ち、value と onChange で結びつける。
          state を空にすれば、入力欄も空になる
        */}
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="やることを追加"
          enterKeyHint="done"
          // text-base（16px）：iPhone は 16px 未満の入力欄をタップすると、画面を勝手に拡大してしまう
          className="min-w-0 flex-1 rounded-lg border border-gray-300 px-3 py-2 text-base outline-none focus:border-brand"
        />
        <button
          type="submit"
          disabled={!title.trim() || create.isPending}
          className="rounded-lg bg-brand px-4 py-2 font-bold text-white disabled:opacity-40"
        >
          追加
        </button>
      </div>

      <label className="flex items-center gap-2 text-sm text-gray-600">
        <input
          type="checkbox"
          checked={withDue}
          onChange={(e) => setWithDue(e.target.checked)}
          className="size-4 accent-brand"
        />
        期限を付ける
      </label>

      {/* 条件 && 部品：条件が true のときだけ表示する */}
      {withDue && (
        <input
          type="datetime-local"
          value={due}
          onChange={(e) => setDue(e.target.value)}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-base"
        />
      )}

      {create.isError && <p className="text-sm text-red-600">追加できませんでした：{create.error.message}</p>}
    </form>
  )
}
