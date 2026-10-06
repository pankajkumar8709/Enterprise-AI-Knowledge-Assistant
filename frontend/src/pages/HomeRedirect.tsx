import { Navigate } from 'react-router-dom';

import { useAuth } from '@/hooks/useAuth';
import { homeForRole } from '@/lib/constants';

/** `/` → dashboard for admins, chat for employees (spec §13.3). */
export function HomeRedirect() {
  const { user } = useAuth();
  return <Navigate to={homeForRole(user?.role)} replace />;
}
