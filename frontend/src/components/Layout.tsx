import { NavLink, Outlet } from 'react-router'

/**
 * すべての画面に共通の枠：上の見出しと、下のタブ。
 * <Outlet /> の場所に、URL に応じた画面（TasksPage など）が入る（main.tsx の children）。
 */
export function Layout() {
  return (
    // min-h-dvh：画面の高さいっぱい。dvh は iPhone の Safari でアドレスバーの出入りに追従する高さの単位
    <div className="flex min-h-dvh flex-col bg-gray-50 text-gray-900">
      {/*
        sticky top-0：スクロールしても上に貼り付いたままにする
        pt-[env(safe-area-inset-top)]：iPhone のノッチ（画面上部の切り欠き）の分だけ余白を取る。
        [] の中には、Tailwind に用意されていない値を直接書ける
      */}
      <header className="sticky top-0 z-10 border-b border-gray-200 bg-white/90 pt-[env(safe-area-inset-top)] backdrop-blur">
        <h1 className="px-4 py-3 text-lg font-bold">クロコさん</h1>
      </header>

      {/* flex-1：残りの高さを全部使う。pb-24：下のタブに中身が隠れないように余白を取る */}
      <main className="mx-auto w-full max-w-xl flex-1 px-4 pt-4 pb-24">
        <Outlet />
      </main>

      <nav className="fixed inset-x-0 bottom-0 border-t border-gray-200 bg-white pb-[env(safe-area-inset-bottom)]">
        <ul className="mx-auto flex max-w-xl">
          <Tab to="/tasks" icon="✅" label="タスク" />
          <Tab icon="🛒" label="買い物" />
          <Tab icon="📅" label="カレンダー" />
          <Tab icon="💬" label="分別" />
        </ul>
      </nav>
    </div>
  )
}

/** 下のタブ1つ分。to がないものは準備中（Phase 2 で作る）。 */
function Tab({ to, icon, label }: { to?: string; icon: string; label: string }) {
  const base = 'flex flex-col items-center gap-0.5 py-2 text-xs'

  if (!to) {
    return (
      <li className="flex-1">
        <span className={`${base} text-gray-300`} aria-disabled="true">
          <span className="text-xl grayscale">{icon}</span>
          {label}
        </span>
      </li>
    )
  }

  return (
    <li className="flex-1">
      {/*
        NavLink：今の URL と to が一致すると isActive が true になるリンク。
        className に関数を渡すと、選ばれているタブだけ色を変えられる
      */}
      <NavLink
        to={to}
        className={({ isActive }) => `${base} ${isActive ? 'font-bold text-brand' : 'text-gray-500'}`}
      >
        <span className="text-xl">{icon}</span>
        {label}
      </NavLink>
    </li>
  )
}
