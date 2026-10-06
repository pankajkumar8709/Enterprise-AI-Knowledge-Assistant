import { useId, type ReactNode } from 'react';

import { cn } from '@/lib/cn';

export interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: 'top' | 'bottom';
  className?: string;
}

/** Hover/focus tooltip for truncated text. The wrapped node stays the source of truth for AT. */
export function Tooltip({ content, children, side = 'top', className }: TooltipProps) {
  const id = useId();
  return (
    <span className={cn('group/tooltip relative inline-flex max-w-full', className)}>
      <span aria-describedby={id} className="inline-flex max-w-full">
        {children}
      </span>
      <span
        id={id}
        role="tooltip"
        className={cn(
          'pointer-events-none absolute left-1/2 z-50 w-max max-w-xs -translate-x-1/2 rounded-lg bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-lg transition group-hover/tooltip:opacity-100 group-focus-within/tooltip:opacity-100',
          side === 'top' ? 'bottom-full mb-1.5' : 'top-full mt-1.5',
        )}
      >
        {content}
      </span>
    </span>
  );
}
