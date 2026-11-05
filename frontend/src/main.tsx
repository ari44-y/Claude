/**
 * 画面の起動口。ここで3つの仕組みを組み立てる。
 *   QueryClientProvider：サーバーのデータのキャッシュ（TanStack Query）を、全部の画面で使えるようにする
 *   RouterProvider：URL に応じて表示する画面を切り替える（React Router）
 *   StrictMode：開発中だけ、よくある間違いを見つけるために処理をわざと2回走らせる
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'

import { Layout } from './components/Layout'
import './index.css'
import { TasksPage } from './pages/TasksPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // 取得して30秒は「新しい」とみなし、画面を切り替えても取り直さない
      retry: 1, // 失敗したら1回だけやり直す
    },
  },
})

// URL と画面の対応表。children の画面は、Layout の <Outlet /> の場所に表示される
const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/tasks" replace /> }, // "/" は "/tasks" へ
      { path: 'tasks', element: <TasksPage /> },
      { path: '*', element: <p className="py-8 text-center text-gray-500">ページが見つかりません</p> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
