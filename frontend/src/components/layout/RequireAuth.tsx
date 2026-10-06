import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { Spinner } from '@/components/ui/Spinner';
import { useAuth } from '@/hooks/useAuth';
import { ROUTES } from '@/lib/constants';

/** Gate for `/app/*` and `/admin/*`: waits for `GET /auth/me`, then redirects. */
export function RequireAuth() {
  const { isAuthenticated, bootstrapping } = useAuth();
  const location = useLocation();

  if (bootstrapping) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3 text-slate-500">
          <Spinner size="lg" label="Restoring your session" />
          <p className="text-sm">Restoring your session…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.login} replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
