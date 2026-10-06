import type { ReactNode } from 'react';

import { cn } from '@/lib/cn';
import type { Source } from '@/types/api';

export interface CitationChipProps {
  children: ReactNode;
  source: Source;
  onOpen: (source: Source) => void;
  className?: string;
}

/** Inline `[1]` marker rendered inside the answer; opens the source drawer. */
export function CitationChip({ children, source, onOpen, className }: CitationChipProps) {
  const label = typeof children === 'string' || typeof children === 'number' ? String(children) : source.ref;
  return (
    <button
      type="button"
      onClick={() => onOpen(source)}
      aria-label={`Open source ${label}`}
      className={cn(
        'mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-md bg-indigo-50 px-1 align-baseline text-[11px] font-semibold text-indigo-700 ring-1 ring-inset ring-indigo-200 transition hover:bg-indigo-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500',
        className,
      )}
    >
      {children}
    </button>
  );
}
