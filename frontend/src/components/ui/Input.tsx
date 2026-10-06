import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react';

import { cn } from '@/lib/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
  icon?: ReactNode;
  suffix?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid, icon, suffix, className, ...props },
  ref,
) {
  return (
    <div className="relative w-full">
      {icon ? (
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">{icon}</span>
      ) : null}
      <input
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cn(
          'focus-ring h-10 w-full rounded-xl border bg-white text-sm text-slate-900 shadow-sm transition placeholder:text-slate-400 disabled:bg-slate-50 disabled:text-slate-500',
          icon ? 'pl-9 pr-3' : 'px-3',
          suffix ? 'pr-10' : '',
          invalid ? 'border-rose-300' : 'border-slate-300',
          className,
        )}
        {...props}
      />
      {suffix ? <span className="absolute right-2 top-1/2 -translate-y-1/2">{suffix}</span> : null}
    </div>
  );
});

export interface FormFieldProps {
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  className?: string;
  /** `id` of the control this label describes (auto-generated when omitted). */
  htmlFor?: string;
  children: ReactNode;
}

/** Label + hint + inline error, wired together for screen readers. */
export function FormField({ label, error, hint, required, className, htmlFor, children }: FormFieldProps) {
  const generated = useId();
  const id = htmlFor ?? generated;
  return (
    <div className={cn('w-full', className)}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
        {required ? (
          <span className="ml-0.5 text-rose-600" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {children}
      {hint && !error ? (
        <p id={`${id}-hint`} className="mt-1.5 text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} role="alert" className="mt-1.5 text-xs font-medium text-rose-600">
          {error}
        </p>
      ) : null}
    </div>
  );
}
