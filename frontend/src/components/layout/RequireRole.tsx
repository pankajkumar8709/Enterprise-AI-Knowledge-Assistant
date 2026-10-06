import { Outlet } from 'react-router-dom';

import { Forbidden } from '@/pages/Forbidden';
import { useAuth } from '@/hooks/useAuth';
import type { Role } from '@/types/api';

/**
 * Role gate for `/admin/*`. Employees are not redirected — they get an explicit
 * 403 page so the mistake is obvious and the URL stays shareable.
 */
export function RequireRole({ role }: { role: Role }) {
  const { user } = useAuth();

  if (!user || user.role !== role) {
    return <Forbidden requiredRole={role} />;
  }

  return <Outlet />;
}
