import { LogOut, Menu, UserRound } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/cn';
import { ROUTES } from '@/lib/constants';
import { useUiStore } from '@/store/uiStore';

export function Topbar() {
  const { user, logout, isAdmin } = useAuth();
  const toggleNav = useUiStore((s) => s.toggleNav);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(event: MouseEvent): void {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false);
    }
    function handleKey(event: KeyboardEvent): void {
      if (event.key === 'Escape') setMenuOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [menuOpen]);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:px-6">
      <button
        type="button"
        onClick={toggleNav}
        aria-label="Open navigation"
        className="focus-ring rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 md:hidden"
      >
        <Menu aria-hidden="true" className="h-5 w-5" />
      </button>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-700">
          {isAdmin ? 'Administration' : 'Knowledge assistant'}
        </p>
      </div>

      <Link
        to={ROUTES.chat}
        className="focus-ring hidden rounded-xl px-3 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 sm:inline-flex"
      >
        Ask a question
      </Link>

      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label="Account menu"
          className="focus-ring flex items-center gap-2 rounded-xl p-1 transition hover:bg-slate-100"
        >
          <Avatar name={user?.full_name ?? 'User'} size="sm" />
          <span className="hidden text-sm font-medium text-slate-700 sm:inline">
            {user?.full_name?.split(' ')[0] ?? 'Account'}
          </span>
        </button>

        {menuOpen ? (
          <div
            role="menu"
            className="absolute right-0 mt-2 w-64 animate-fade-in rounded-2xl border border-slate-200 bg-white p-2 shadow-xl"
          >
            <div className="flex items-start gap-3 rounded-xl px-3 py-2">
              <Avatar name={user?.full_name ?? 'User'} />
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-900">{user?.full_name ?? '—'}</p>
                <p className="truncate text-xs text-slate-500">{user?.email ?? ''}</p>
                <Badge color={isAdmin ? 'indigo' : 'sky'} size="sm" className="mt-1.5">
                  {user?.role ?? 'employee'}
                </Badge>
              </div>
            </div>
            <div className="my-1 h-px bg-slate-100" />
            <Link
              to={ROUTES.library}
              role="menuitem"
              onClick={() => setMenuOpen(false)}
              className={cn(
                'focus-ring flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-100',
              )}
            >
              <UserRound aria-hidden="true" className="h-4 w-4" /> My library
            </Link>
            <Button
              variant="ghost"
              block
              role="menuitem"
              icon={<LogOut aria-hidden="true" className="h-4 w-4" />}
              className="justify-start"
              onClick={() => {
                setMenuOpen(false);
                void logout();
              }}
            >
              Sign out
            </Button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
