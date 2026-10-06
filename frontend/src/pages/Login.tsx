import { zodResolver } from '@hookform/resolvers/zod';
import { Eye, EyeOff, Lock, Mail, ShieldCheck, Sparkles, TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { z } from 'zod';

import { Button } from '@/components/ui/Button';
import { FormField, Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { useAuth } from '@/hooks/useAuth';
import { apiErrorMessage } from '@/lib/api';
import { APP_NAME, APP_TAGLINE, homeForRole, ROUTES } from '@/lib/constants';

const loginSchema = z.object({
  email: z.string().trim().min(1, 'Email is required').email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});

type LoginValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  const { login, isAuthenticated, user, bootstrapping } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const expired = params.get('expired') === '1';

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema), defaultValues: { email: '', password: '' } });

  if (!bootstrapping && isAuthenticated) {
    const from = (location.state as { from?: string } | null)?.from;
    return <Navigate to={from ?? homeForRole(user?.role)} replace />;
  }

  const submit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const signedIn = await login(values.email, values.password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? homeForRole(signedIn.role), { replace: true });
    } catch (error) {
      setFormError(apiErrorMessage(error, 'Email or password is incorrect.'));
    }
  });

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between bg-gradient-to-br from-indigo-600 via-indigo-700 to-violet-800 p-10 text-white lg:flex">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15">
            <ShieldCheck aria-hidden="true" className="h-5 w-5" />
          </span>
          <span className="text-base font-semibold">{APP_NAME}</span>
        </div>

        <div className="max-w-md space-y-4">
          <h1 className="text-3xl font-semibold tracking-tight">Answers your team can trust</h1>
          <p className="text-indigo-100">{APP_TAGLINE}</p>
          <ul className="space-y-3 text-sm text-indigo-50">
            <li className="flex items-start gap-2">
              <Sparkles aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
              Hybrid retrieval over documents <em>and</em> reviewed facts
            </li>
            <li className="flex items-start gap-2">
              <Sparkles aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
              Every answer cites the passage it came from
            </li>
            <li className="flex items-start gap-2">
              <Sparkles aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
              Access rules enforced per department
            </li>
          </ul>
        </div>

        <p className="text-xs text-indigo-200">Access is limited to your organisation&apos;s knowledge.</p>
      </div>

      <div className="flex items-center justify-center bg-slate-50 p-4 sm:p-8">
        <div className="w-full max-w-md">
          <div className="mb-6 lg:hidden">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white">
              <ShieldCheck aria-hidden="true" className="h-5 w-5" />
            </span>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-900">{APP_NAME}</h1>
            <p className="mt-1 text-sm text-slate-500">{APP_TAGLINE}</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">Sign in</h2>
            <p className="mt-0.5 text-sm text-slate-500">Use your work email address.</p>

            {expired ? (
              <div
                role="status"
                className="mt-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900"
              >
                <TriangleAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
                Your session expired. Please sign in again.
              </div>
            ) : null}

            {formError ? (
              <div
                role="alert"
                className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-800"
              >
                {formError}
              </div>
            ) : null}

            <form noValidate className="mt-5 space-y-4" onSubmit={(event) => void submit(event)}>
              <FormField label="Email" error={errors.email?.message} required htmlFor="login-email">
                <Input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@company.com"
                  icon={<Mail aria-hidden="true" className="h-4 w-4" />}
                  invalid={Boolean(errors.email)}
                  {...register('email')}
                />
              </FormField>

              <FormField label="Password" error={errors.password?.message} required htmlFor="login-password">
                <Input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••••"
                  icon={<Lock aria-hidden="true" className="h-4 w-4" />}
                  invalid={Boolean(errors.password)}
                  suffix={
                    <button
                      type="button"
                      onClick={() => setShowPassword((shown) => !shown)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className="focus-ring rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                    >
                      {showPassword ? (
                        <EyeOff aria-hidden="true" className="h-4 w-4" />
                      ) : (
                        <Eye aria-hidden="true" className="h-4 w-4" />
                      )}
                    </button>
                  }
                  {...register('password')}
                />
              </FormField>

              <Button type="submit" block size="lg" loading={isSubmitting}>
                {isSubmitting ? 'Signing in…' : 'Sign in'}
              </Button>
            </form>

            <p className="mt-5 text-center text-sm text-slate-500">
              Need an account?{' '}
              <Link to={ROUTES.signup} className="focus-ring rounded font-medium text-indigo-700 hover:underline">
                Create one
              </Link>
            </p>
          </div>

          {bootstrapping ? (
            <p className="mt-4 flex items-center justify-center gap-2 text-xs text-slate-500">
              <Spinner /> Checking your session…
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
