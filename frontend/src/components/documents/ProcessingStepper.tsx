import { Check, X } from 'lucide-react';

import { Badge } from '@/components/ui/Badge';
import { ProgressSteps } from '@/components/ui/ProgressSteps';
import { cn } from '@/lib/cn';
import { STAGE_LABEL, STAGE_ORDER } from '@/lib/constants';
import type { DocStage, DocStatus } from '@/types/api';

const STEP_ITEMS = STAGE_ORDER.map((stage) => ({ key: stage, label: STAGE_LABEL[stage] }));

/** Stage index for the stepper; `done`/`ready` completes every step. */
export function stageIndex(stage: DocStage | null | undefined, status: DocStatus): number {
  if (status === 'ready' || stage === 'done') return STAGE_ORDER.length;
  if (!stage) return 0;
  const index = STAGE_ORDER.indexOf(stage);
  return index < 0 ? 0 : index;
}

export interface ProcessingStepperProps {
  stage: DocStage | null;
  status: DocStatus;
  variant?: 'compact' | 'full';
  className?: string;
}

/**
 * Six-stage ingestion stepper (Extracting → Cleaning → Chunking → Embedding →
 * Facts → Indexing). Compact mode is the row chip; full mode is the detail view.
 */
export function ProcessingStepper({ stage, status, variant = 'compact', className }: ProcessingStepperProps) {
  const current = stageIndex(stage, status);
  const failed = status === 'failed';
  const complete = status === 'ready' || (!failed && current >= STAGE_ORDER.length);

  if (variant === 'full') {
    return (
      <ProgressSteps
        steps={STEP_ITEMS}
        currentIndex={current}
        failed={failed}
        className={className}
        aria-label="Ingestion progress"
      />
    );
  }

  if (status === 'ready') {
    return (
      <Badge color="emerald" className={className}>
        <Check aria-hidden="true" className="h-3 w-3" />
        All stages complete
      </Badge>
    );
  }

  if (failed) {
    return (
      <Badge color="rose" className={className}>
        <X aria-hidden="true" className="h-3 w-3" />
        Failed at {STAGE_LABEL[STAGE_ORDER[Math.min(current, STAGE_ORDER.length - 1)] ?? 'extracting']}
      </Badge>
    );
  }

  if (status === 'uploaded') {
    return (
      <Badge color="slate" className={className}>
        Waiting to start
      </Badge>
    );
  }

  const currentStage = STAGE_ORDER[Math.min(current, STAGE_ORDER.length - 1)] ?? 'extracting';

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="flex items-center gap-0.5" aria-hidden="true">
        {STEP_ITEMS.map((step, index) => (
          <span
            key={step.key}
            className={cn(
              'h-1.5 w-3 rounded-full',
              index < current
                ? 'bg-emerald-400'
                : index === current
                  ? 'animate-pulse bg-indigo-500'
                  : 'bg-slate-200',
            )}
          />
        ))}
      </span>
      <span className="text-xs font-medium text-indigo-700">{STAGE_LABEL[currentStage]}</span>
      <span className="sr-only">
        Stage {current + 1} of {STAGE_ORDER.length}: {STAGE_LABEL[currentStage]}
        {complete ? ' (complete)' : ''}
      </span>
    </div>
  );
}
