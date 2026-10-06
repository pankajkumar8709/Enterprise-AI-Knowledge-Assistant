import { useMemo, useState } from 'react';

import { OkfForm } from '@/components/knowledge/OkfForm';
import { ReviewQueue } from '@/components/knowledge/ReviewQueue';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import {
  KNOWLEDGE_FETCH_LIMIT,
  useApproveKnowledge,
  useBulkReviewKnowledge,
  useKnowledgeQuery,
  useRejectKnowledge,
} from '@/hooks/useKnowledge';
import { formatNumber } from '@/lib/format';
import type { OkfObjectDto } from '@/types/api';

export function KnowledgeReviewPage() {
  const knowledge = useKnowledgeQuery();
  const approve = useApproveKnowledge();
  const reject = useRejectKnowledge();
  const bulk = useBulkReviewKnowledge();
  const [editing, setEditing] = useState<OkfObjectDto | null>(null);

  const pending = useMemo(
    () => (knowledge.data?.items ?? []).filter((object) => object.status === 'pending_review'),
    [knowledge.data],
  );

  const busyId = approve.isPending
    ? (approve.variables?.id ?? null)
    : reject.isPending
      ? (reject.variables?.id ?? null)
      : null;

  const truncated = (knowledge.data?.total ?? 0) > KNOWLEDGE_FETCH_LIMIT;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Review queue"
        description="Facts extracted from documents wait here. Only approved objects can be cited in chat answers."
        actions={
          <Badge color={pending.length ? 'amber' : 'emerald'}>
            {formatNumber(pending.length)} pending
          </Badge>
        }
      />

      {truncated ? (
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Showing the {KNOWLEDGE_FETCH_LIMIT} most recent objects. Older pending items appear here as you clear the queue.
        </p>
      ) : null}

      <ReviewQueue
        objects={pending}
        loading={knowledge.isPending}
        error={knowledge.error}
        onRetry={() => void knowledge.refetch()}
        busyId={busyId}
        bulkPending={bulk.isPending}
        onApprove={(object) => approve.mutate({ id: object.id })}
        onReject={(object) => reject.mutate({ id: object.id })}
        onEdit={(object) => setEditing(object)}
        onBulkAction={(ids, action) => bulk.mutate({ ids, action })}
      />

      <OkfForm open={editing !== null} object={editing} onClose={() => setEditing(null)} />
    </div>
  );
}
