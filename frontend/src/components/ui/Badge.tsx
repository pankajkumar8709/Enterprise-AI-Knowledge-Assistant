import { cva, type VariantProps } from 'class-variance-authority';
import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '@/lib/cn';

const badge = cva(
  'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
  {
    variants: {
      color: {
        slate: 'bg-slate-50 text-slate-700 ring-slate-200',
        indigo: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
        emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
        amber: 'bg-amber-50 text-amber-800 ring-amber-200',
        rose: 'bg-rose-50 text-rose-700 ring-rose-200',
        sky: 'bg-sky-50 text-sky-700 ring-sky-200',
        violet: 'bg-violet-50 text-violet-700 ring-violet-200',
      },
      size: {
        sm: 'px-2 py-0.5 text-[11px]',
        md: 'px-2.5 py-0.5 text-xs',
      },
    },
    defaultVariants: { color: 'slate', size: 'md' },
  },
);

export type BadgeProps = HTMLAttributes<HTMLSpanElement> &
  VariantProps<typeof badge> & {
    dot?: ReactNode;
  };

export function Badge({ color, size, dot, className, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badge({ color, size }), className)} {...props}>
      {dot}
      {children}
    </span>
  );
}
