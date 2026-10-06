import { forwardRef, type TextareaHTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { invalid, className, rows = 4, ...props },
  ref,
) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      aria-invalid={invalid || undefined}
      className={cn(
        'focus-ring w-full resize-y rounded-xl border bg-white px-3 py-2 text-sm leading-6 text-slate-900 shadow-sm transition placeholder:text-slate-400 disabled:bg-slate-50 disabled:text-slate-500',
        invalid ? 'border-rose-300' : 'border-slate-300',
        className,
      )}
      {...props}
    />
  );
});
