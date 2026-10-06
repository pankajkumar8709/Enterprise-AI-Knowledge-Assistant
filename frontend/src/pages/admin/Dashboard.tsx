import { AlertOctagon, CheckCircle2, ClipboardCheck, Loader2, TriangleAlert } from 'lucide-react';
import { Link } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import { StatusBadge } from '@/components/documents/StatusBadge';
import { Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { StatCard } from '@/components/ui/StatCard';
import { useAdminStatsQuery } from '@/hooks/useAdmin';
import { useDocumentsQuery } from '@/hooks/useDocuments';
import { ROUTES } from '@/lib/constants';
import { formatDateTime, formatNumber } from '@/lib/format';

export function DashboardPage() {
  const stats = useAdminStatsQuery();
  const documents = useDocumentsQuery();

  const items = documents.data?.items ?? [];
  const recent = [...items].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
  const failed = items.filter((document) => document.status === 'failed');
  const pendingReviews = stats.data?.okf.pending ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Corpus health, ingestion activity and the knowledge objects waiting for review."
      />

      <section aria-label="Key metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Documents ready"
          value={formatNumber(stats.data?.documents.ready ?? 0)}
          icon={<CheckCircle2 aria-hidden="true" className="h-5 w-5" />}
          tone="emerald"
          loading={stats.isPending}
          hint={`${formatNumber(stats.data?.documents.total ?? 0)} total`}
        />
        <StatCard
          label="Processing"
          value={formatNumber(stats.data?.documents.processing ?? 0)}
          icon={<Loader2 aria-hidden="true" className="h-5 w-5" />}
          tone="sky"
          loading={stats.isPending}
          hint="Live status updates every 3 s"
        />
        <StatCard
          label="Failed"
          value={formatNumber(stats.data?.documents.failed ?? 0)}
          icon={<AlertOctagon aria-hidden="true" className="h-5 w-5" />}
          tone="rose"
          loading={stats.isPending}
          hint={failed.length ? 'Reprocess from Documents' : 'Nothing needs attention'}
        />
        <StatCard
          label="Pending reviews"
          value={formatNumber(pendingReviews)}
          icon={<ClipboardCheck aria-hidden="true" className="h-5 w-5" />}
          tone="amber"
          loading={stats.isPending}
          hint="Approve before chat can cite them"
        />
      </section>

      {stats.error ? (
        <ErrorState message="Could not load the dashboard metrics." onRetry={() => void stats.refetch()} compact />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Recent uploads</CardTitle>
              <p className="mt-0.5 text-sm text-slate-500">The five newest documents.</p>
            </div>
            <Link to={ROUTES.documents} className="focus-ring rounded text-sm font-medium text-indigo-700 hover:underline">
              View all
            </Link>
          </CardHeader>
          <CardBody className="pt-2">
            {documents.isPending ? (
              <div className="space-y-3">
                {[0, 1, 2, 3, 4].map((index) => (
                  <Skeleton key={index} className="h-10 w-full rounded-xl" />
                ))}
              </div>
            ) : documents.error ? (
              <ErrorState compact message="Could not load recent uploads." onRetry={() => void documents.refetch()} />
            ) : !recent.length ? (
              <EmptyState
                icon={<TriangleAlert aria-hidden="true" className="h-5 w-5" />}
                title="No documents yet"
                hint="Upload your first document to populate the knowledge base."
              />
            ) : (
              <ul className="divide-y divide-slate-100">
                {recent.map((document) => (
                  <li key={document.id} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <Link
                        to={ROUTES.document(document.id)}
                        className="focus-ring block truncate rounded text-sm font-medium text-slate-800 hover:text-indigo-700"
                      >
                        {document.title}
                      </Link>
                      <p className="text-xs text-slate-500">{formatDateTime(document.created_at)}</p>
                    </div>
                    <StatusBadge status={document.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Needs attention</CardTitle>
              <p className="mt-0.5 text-sm text-slate-500">Failures and objects waiting for review.</p>
            </div>
          </CardHeader>
          <CardBody className="space-y-3 pt-2">
            {failed.length ? (
              <div className="space-y-2">
                {failed.slice(0, 3).map((document) => (
                  <Link
                    key={document.id}
                    to={ROUTES.document(document.id)}
                    className="focus-ring flex items-start justify-between gap-3 rounded-xl border border-rose-100 bg-rose-50/60 px-3 py-2 transition hover:bg-rose-50"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-rose-900">{document.title}</span>
                      <span className="block truncate text-xs text-rose-700">
                        {document.chunking_error ?? document.extraction_error ?? 'Processing failed'}
                      </span>
                    </span>
                    <Badge color="rose" size="sm">
                      failed
                    </Badge>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="rounded-xl border border-emerald-100 bg-emerald-50/60 px-3 py-2 text-sm text-emerald-800">
                No failed documents. Ingestion is healthy.
              </p>
            )}

            <Link
              to={ROUTES.knowledgeReview}
              className="focus-ring flex items-center justify-between gap-3 rounded-xl border border-amber-100 bg-amber-50/70 px-3 py-2.5 transition hover:bg-amber-50"
            >
              <span>
                <span className="block text-sm font-medium text-amber-900">
                  {formatNumber(pendingReviews)} knowledge {pendingReviews === 1 ? 'object' : 'objects'} pending review
                </span>
                <span className="block text-xs text-amber-800">Approve them so chat can cite the facts.</span>
              </span>
              <Badge color="amber" size="sm">
                review
              </Badge>
            </Link>

            <p className="text-xs text-slate-500">
              {formatNumber(stats.data?.queries_7d ?? 0)} questions asked in the last 7 days ·{' '}
              {formatNumber(stats.data?.users ?? 0)} users
            </p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
