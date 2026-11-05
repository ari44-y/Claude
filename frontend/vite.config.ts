import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
// vitest/config の defineConfig は、Vite の設定に test（Vitest の設定）を足せる版
export default defineConfig({
  plugins: [
    react(), // JSX の変換と、保存したら画面だけ差し替える機能（HMR）
    tailwindcss(), // CSS の中の @import "tailwindcss" を、実際に使ったクラスの CSS に変換する
  ],
  server: {
    // 開発時：画面は Vite（:5173）、API は FastAPI（:8000）で別々に動く。
    // 画面から /api/... を呼んだら FastAPI に中継する。
    // こうすると本番（FastAPI が画面も配信する）と同じ URL のまま開発できる
    // 中継先は環境変数 API_ORIGIN で変えられる。
    // Docker の開発環境では compose.yaml が http://backend:8000（API のコンテナ）を設定する
    proxy: {
      '/api': process.env.API_ORIGIN ?? 'http://localhost:8000',
    },
  },
  test: {
    include: ['src/**/*.test.ts'],
  },
})
