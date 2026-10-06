import { AlertTriangle, RotateCw } from 'lucide-react';

import { cn } from '@/lib/cn';

import { Button } from './Button';

export interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  className?: string;
  compact?: boolean;
}

export function ErrorState({ message, onRetry, className, compact = false }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center gap-3 px-6 text-center',
        compact ? 'py-6' : 'py-12',
        className,
      )}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-50 text-rose-600">
        <AlertTriangle aria-hidden="true" className="h-5 w-5" />
      </span>
      <div>
        <p className="text-sm font-semibold text-slate-900">Couldn&apos;t load this</p>
        <p className="mt-1 max-w-sm text-sm text-slate-500">{message}</p>
      </div>
      {onRetry ? (
        <Button variant="secondary" size="sm" icon={<RotateCw className="h-3.5 w-3.5" />} onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
