import { CheckCheck, Inbox } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { pluralize } from '@/lib/format';
import type { OkfObjectDto } from '@/types/api';

import { OkfCard } from './OkfCard';

export interface ReviewQueueProps {
  objects: OkfObjectDto[];
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  onApprove: (object: OkfObjectDto) => void;
  onReject: (object: OkfObjectDto) => void;
  onEdit: (object: OkfObjectDto) => void;
  onBulkAction: (ids: number[], action: 'approve' | 'reject') => void;
  bulkPending?: boolean;
  busyId?: number | null;
}

/** Grid of pending objects (2 columns on `xl`) plus a sticky bulk-action bar. */
export function ReviewQueue({
  objects,
  loading,
  error,
  onRetry,
  onApprove,
  onReject,
  onEdit,
  onBulkAction,
  bulkPending = false,
  busyId = null,
}: ReviewQueueProps) {
  const [selected, setSelected] = useState<number[]>([]);

  if (loading) {
    return (
      <div className="grid gap-4 xl:grid-cols-2">
        {[0, 1, 2, 3].map((index) => (
          <div key={index} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5">
            <Skeleton className="h-5 w-24 rounded-full" />
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return <ErrorState message="Could not load the review queue." onRetry={onRetry} />;
  }

  if (!objects.length) {
    return (
      <EmptyState
        icon={<CheckCheck aria-hidden="true" className="h-5 w-5" />}
        title="Nothing to review"
        hint="Extracted facts land here for approval before chat can cite them."
      />
    );
  }

  const toggle = (id: number, isSelected: boolean) =>
    setSelected((current) => (isSelected ? [...current, id] : current.filter((item) => item !== id)));

  return (
    <div className="space-y-4 pb-20">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-slate-500">
          {objects.length} {pluralize(objects.length, 'object')} waiting for review
        </p>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSelected(selected.length === objects.length ? [] : objects.map((o) => o.id))}
        >
          {selected.length === objects.length ? 'Clear selection' : 'Select all'}
        </Button>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {objects.map((object) => (
          <OkfCard
            key={object.id}
            object={object}
            selectable
            selected={selected.includes(object.id)}
            onToggleSelect={toggle}
            onApprove={onApprove}
            onReject={onReject}
            onEdit={onEdit}
            busy={busyId === object.id}
          />
        ))}
      </div>

      {selected.length ? (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 px-4 py-3 shadow-xl backdrop-blur lg:px-6">
          <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-sm font-medium text-slate-700">
              <Inbox aria-hidden="true" className="h-4 w-4 text-indigo-600" />
              {selected.length} {pluralize(selected.length, 'object')} selected
            </p>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={() => setSelected([])} disabled={bulkPending}>
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                loading={bulkPending}
                onClick={() => {
                  onBulkAction(selected, 'reject');
                  setSelected([]);
                }}
              >
                Reject selected
              </Button>
              <Button
                size="sm"
                loading={bulkPending}
                onClick={() => {
                  onBulkAction(selected, 'approve');
                  setSelected([]);
                }}
              >
                Approve selected
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
