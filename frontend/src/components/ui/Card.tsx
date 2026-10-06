import { cva, type VariantProps } from 'class-variance-authority';
import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

const card = cva('rounded-2xl border bg-white transition-shadow', {
  variants: {
    tone: {
      default: 'border-slate-200 shadow-sm',
      elevated: 'border-slate-200 shadow-md',
      accent: 'border-indigo-200 bg-indigo-50/40',
      danger: 'border-rose-200 bg-rose-50/50',
    },
    interactive: {
      true: 'cursor-pointer hover:border-slate-300 hover:shadow-md',
      false: '',
    },
  },
  defaultVariants: { tone: 'default', interactive: false },
});

export type CardProps = HTMLAttributes<HTMLDivElement> & VariantProps<typeof card>;

export function Card({ tone, interactive, className, ...props }: CardProps) {
  return <div className={cn(card({ tone, interactive }), className)} {...props} />;
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex items-start justify-between gap-3 px-5 pt-5', className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn('text-lg font-semibold text-slate-900', className)} {...props} />;
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('mt-0.5 text-sm text-slate-500', className)} {...props} />;
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-5 text-sm leading-6 text-slate-700', className)} {...props} />;
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex flex-wrap items-center gap-2 border-t border-slate-100 px-5 py-4', className)}
      {...props}
    />
  );
}
