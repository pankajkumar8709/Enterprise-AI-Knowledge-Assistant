import { Outlet } from 'react-router-dom';

import { Drawer } from '@/components/ui/Drawer';
import { Toaster } from '@/components/ui/Toast';
import { useUiStore } from '@/store/uiStore';

import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

/**
 * Shell for every authenticated page: sidebar (rail < lg, drawer < md), sticky
 * topbar, and the page container with `p-4` / `p-6` padding.
 */
export function AppShell() {
  const navOpen = useUiStore((s) => s.navOpen);
  const setNavOpen = useUiStore((s) => s.setNavOpen);

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-slate-200 bg-white md:flex md:w-16 lg:w-64">
        <Sidebar compact />
      </aside>

      <Drawer
        open={navOpen}
        onClose={() => setNavOpen(false)}
        title="Navigation"
        side="left"
        widthClassName="w-72"
        className="md:hidden"
      >
        <div className="-mx-5 -my-4">
          <Sidebar onNavigate={() => setNavOpen(false)} />
        </div>
      </Drawer>

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="mx-auto w-full max-w-[1400px] flex-1 p-4 lg:p-6">
          <Outlet />
        </main>
      </div>

      <Toaster />
    </div>
  );
}
