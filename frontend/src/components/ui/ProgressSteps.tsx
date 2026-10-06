import { Check, X } from 'lucide-react';

import { cn } from '@/lib/cn';

export interface ProgressStep {
  key: string;
  label: string;
}

export interface ProgressStepsProps {
  steps: readonly ProgressStep[];
  /** Index of the running step; `steps.length` means every step is complete. */
  currentIndex: number;
  failed?: boolean;
  orientation?: 'horizontal' | 'vertical';
  className?: string;
  'aria-label'?: string;
}

export function ProgressSteps({
  steps,
  currentIndex,
  failed = false,
  orientation = 'horizontal',
  className,
  'aria-label': ariaLabel,
}: ProgressStepsProps) {
  if (orientation === 'vertical') {
    return (
      <ol aria-label={ariaLabel} className={cn('space-y-3', className)}>
        {steps.map((step, index) => {
          const state = index < currentIndex ? 'done' : index === currentIndex ? 'current' : 'todo';
          return (
            <li key={step.key} className="flex items-center gap-3">
              <Marker state={state} failed={failed} index={index} />
              <span
                className={cn(
                  'text-sm',
                  state === 'todo' ? 'text-slate-400' : 'font-medium text-slate-700',
                  failed && index === currentIndex ? 'text-rose-600' : '',
                )}
              >
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
    );
  }

  return (
    <ol aria-label={ariaLabel} className={cn('flex flex-wrap items-center gap-x-3 gap-y-2', className)}>
      {steps.map((step, index) => {
        const state = index < currentIndex ? 'done' : index === currentIndex ? 'current' : 'todo';
        return (
          <li key={step.key} className="flex items-center gap-2">
            <Marker state={state} failed={failed} index={index} />
            <span
              className={cn(
                'text-xs',
                state === 'current'
                  ? failed
                    ? 'font-medium text-rose-600'
                    : 'font-medium text-indigo-700'
                  : state === 'done'
                    ? 'text-slate-600'
                    : 'text-slate-400',
              )}
            >
              {step.label}
            </span>
            {index < steps.length - 1 ? <span aria-hidden="true" className="h-px w-4 bg-slate-200" /> : null}
          </li>
        );
      })}
    </ol>
  );
}

function Marker({
  state,
  failed,
  index,
}: {
  state: 'done' | 'current' | 'todo';
  failed: boolean;
  index: number;
}) {
  if (state === 'done') {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
        <Check aria-hidden="true" className="h-3 w-3" />
        <span className="sr-only">step {index + 1} complete</span>
      </span>
    );
  }
  if (state === 'current') {
    return failed ? (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-rose-100 text-rose-700">
        <X aria-hidden="true" className="h-3 w-3" />
        <span className="sr-only">step {index + 1} failed</span>
      </span>
    ) : (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-100">
        <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-600" />
        <span className="sr-only">step {index + 1} in progress</span>
      </span>
    );
  }
  return (
    <span className="flex h-5 w-5 items-center justify-center rounded-full border border-slate-200 bg-white">
      <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
      <span className="sr-only">step {index + 1} pending</span>
    </span>
  );
}
