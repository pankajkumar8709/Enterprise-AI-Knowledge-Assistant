import { ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';

import { buttonVariants } from '@/components/ui/Button';
import { useUiStore } from '@/store/uiStore';
import { homeForRole } from '@/lib/constants';
import { useAuth } from '@/hooks/useAuth';
import type { Role } from '@/types/api';

/** Rendered in place of `/admin/*` for non-admin users (spec §13.3). */
export function Forbidden({ requiredRole }: { requiredRole?: Role }) {
  const { user } = useAuth();
  const setNavOpen = useUiStore((s) => s.setNavOpen);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-50 text-amber-600">
        <ShieldAlert aria-hidden="true" className="h-6 w-6" />
      </span>
      <h1 className="mt-4 text-2xl font-semibold tracking-tight text-slate-900">You don&apos;t have access</h1>
      <p className="mt-1 max-w-md text-sm text-slate-500">
        This area is limited to {requiredRole ?? 'admin'} accounts. You are signed in
        {user?.role ? ` as ${user.role}` : ''} — ask an administrator if you need access.
      </p>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        <Link to={homeForRole(user?.role)} className={buttonVariants({ variant: 'primary' })}>
          Back to your workspace
        </Link>
        <button type="button" className={buttonVariants({ variant: 'secondary' })} onClick={() => setNavOpen(true)}>
          Open navigation
        </button>
      </div>
    </div>
  );
}
