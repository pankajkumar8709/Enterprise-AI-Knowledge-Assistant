import type { ReactNode } from 'react';

import { Card } from './Card';
import { Skeleton } from './Skeleton';

export interface StatCardProps {
  label: string;
  value: string | number;
  icon: ReactNode;
  hint?: string;
  loading?: boolean;
  /** Colour of the icon tile; defaults to indigo. */
  tone?: 'indigo' | 'emerald' | 'sky' | 'rose' | 'amber';
  onClick?: () => void;
}

const TONES = {
  indigo: 'bg-indigo-50 text-indigo-600',
  emerald: 'bg-emerald-50 text-emerald-600',
  sky: 'bg-sky-50 text-sky-600',
  rose: 'bg-rose-50 text-rose-600',
  amber: 'bg-amber-50 text-amber-600',
} as const;

export function StatCard({ label, value, icon, hint, loading = false, tone = 'indigo', onClick }: StatCardProps) {
  const interactive = Boolean(onClick);
  return (
    <Card
      interactive={interactive}
      className="p-5"
      {...(onClick
        ? {
            role: 'button',
            tabIndex: 0,
            onClick,
            onKeyDown: (event: React.KeyboardEvent<HTMLDivElement>) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onClick();
              }
            },
          }
        : {})}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
          {loading ? (
            <Skeleton className="mt-2 h-8 w-16" />
          ) : (
            <p className="mt-1 text-3xl font-bold tabular-nums text-slate-900">{value}</p>
          )}
          {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
        </div>
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${TONES[tone]}`}>{icon}</span>
      </div>
    </Card>
  );
}
