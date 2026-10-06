import { zodResolver } from '@hookform/resolvers/zod';
import { Eye, EyeOff, Lock, Mail, ShieldCheck, UserRound } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { Button } from '@/components/ui/Button';
import { FormField, Input } from '@/components/ui/Input';
import { useAuth } from '@/hooks/useAuth';
import { apiErrorMessage } from '@/lib/api';
import { APP_NAME, homeForRole, ROUTES } from '@/lib/constants';

/** Mirrors the backend rule: ≥10 chars, one uppercase letter, one digit. */
const signupSchema = z
  .object({
    full_name: z.string().trim().min(2, 'Enter your full name').max(120, 'Keep this under 120 characters'),
    email: z.string().trim().min(1, 'Email is required').email('Enter a valid email address'),
    password: z
      .string()
      .min(10, 'Use at least 10 characters')
      .regex(/[A-Z]/, 'Include at least one uppercase letter')
      .regex(/\d/, 'Include at least one digit'),
    confirm: z.string(),
  })
  .refine((values) => values.password === values.confirm, {
    message: 'Passwords do not match',
    path: ['confirm'],
  });

type SignupValues = z.infer<typeof signupSchema>;

export function SignupPage() {
  const { signup, isAuthenticated, user, bootstrapping } = useAuth();
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { full_name: '', email: '', password: '', confirm: '' },
  });

  if (!bootstrapping && isAuthenticated) {
    return <Navigate to={homeForRole(user?.role)} replace />;
  }

  const submit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const created = await signup({
        full_name: values.full_name.trim(),
        email: values.email.trim(),
        password: values.password,
      });
      navigate(homeForRole(created.role), { replace: true });
    } catch (error) {
      setFormError(apiErrorMessage(error, 'Sign-up failed. Please try again.'));
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
        <div className="max-w-md space-y-3">
          <h1 className="text-3xl font-semibold tracking-tight">Start asking better questions</h1>
          <p className="text-indigo-100">
            New accounts are created as employees. An administrator can widen your access later.
          </p>
        </div>
        <p className="text-xs text-indigo-200">Need admin access? Ask your workspace owner.</p>
      </div>

      <div className="flex items-center justify-center bg-slate-50 p-4 sm:p-8">
        <div className="w-full max-w-md">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">Create your account</h2>
            <p className="mt-0.5 text-sm text-slate-500">Signing up is only available when self-signup is enabled.</p>

            {formError ? (
              <div
                role="alert"
                className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-800"
              >
                {formError}
              </div>
            ) : null}

            <form noValidate className="mt-5 space-y-4" onSubmit={(event) => void submit(event)}>
              <FormField label="Full name" error={errors.full_name?.message} required htmlFor="signup-name">
                <Input
                  id="signup-name"
                  autoComplete="name"
                  placeholder="Asha Verma"
                  icon={<UserRound aria-hidden="true" className="h-4 w-4" />}
                  invalid={Boolean(errors.full_name)}
                  {...register('full_name')}
                />
              </FormField>

              <FormField label="Email" error={errors.email?.message} required htmlFor="signup-email">
                <Input
                  id="signup-email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@company.com"
                  icon={<Mail aria-hidden="true" className="h-4 w-4" />}
                  invalid={Boolean(errors.email)}
                  {...register('email')}
                />
              </FormField>

              <FormField
                label="Password"
                error={errors.password?.message}
                hint="At least 10 characters, one uppercase letter and one digit."
                required
                htmlFor="signup-password"
              >
                <Input
                  id="signup-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
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

              <FormField label="Confirm password" error={errors.confirm?.message} required htmlFor="signup-confirm">
                <Input
                  id="signup-confirm"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="••••••••••"
                  icon={<Lock aria-hidden="true" className="h-4 w-4" />}
                  invalid={Boolean(errors.confirm)}
                  {...register('confirm')}
                />
              </FormField>

              <Button type="submit" block size="lg" loading={isSubmitting}>
                {isSubmitting ? 'Creating account…' : 'Create account'}
              </Button>
            </form>

            <p className="mt-5 text-center text-sm text-slate-500">
              Already have an account?{' '}
              <Link to={ROUTES.login} className="focus-ring rounded font-medium text-indigo-700 hover:underline">
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
