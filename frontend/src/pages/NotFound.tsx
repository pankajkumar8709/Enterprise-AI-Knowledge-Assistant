import { Compass } from 'lucide-react';
import { Link } from 'react-router-dom';

import { buttonVariants } from '@/components/ui/Button';
import { homeForRole } from '@/lib/constants';
import { useAuth } from '@/hooks/useAuth';

export function NotFoundPage() {
  const { user } = useAuth();

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">
        <Compass aria-hidden="true" className="h-6 w-6" />
      </span>
      <h1 className="mt-4 text-2xl font-semibold tracking-tight text-slate-900">Page not found</h1>
      <p className="mt-1 max-w-md text-sm text-slate-500">
        The page you were looking for doesn&apos;t exist or has been moved.
      </p>
      <Link to={homeForRole(user?.role)} className={`mt-5 ${buttonVariants({ variant: 'primary' })}`}>
        Go to your workspace
      </Link>
    </div>
  );
}
