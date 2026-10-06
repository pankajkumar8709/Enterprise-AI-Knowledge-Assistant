import { ArrowLeft, Archive, Check, History, Pencil, X } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { AttributeTable } from '@/components/knowledge/AttributeTable';
import { OkfForm } from '@/components/knowledge/OkfForm';
import { OkfHeader } from '@/components/knowledge/OkfCard';
import { SourceQuote } from '@/components/knowledge/SourceQuote';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Drawer } from '@/components/ui/Drawer';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDocumentQuery } from '@/hooks/useDocuments';
import {
  useApproveKnowledge,
  useArchiveKnowledge,
  useKnowledgeItemQuery,
  useKnowledgeVersionsQuery,
  useRejectKnowledge,
} from '@/hooks/useKnowledge';
import { ROUTES, VISIBILITY_LABEL } from '@/lib/constants';
import { formatDateTime, formatPercent } from '@/lib/format';

export function KnowledgeDetailPage() {
  const { knowledgeId } = useParams<{ knowledgeId: string }>();
  const navigate = useNavigate();
  const id = knowledgeId ? Number(knowledgeId) : NaN;
  const validId = Number.isFinite(id) ? id : null;

  const object = useKnowledgeItemQuery(validId);
  const versions = useKnowledgeVersionsQuery(validId);
  const document = useDocumentQuery(object.data?.source_document_id ?? null);
  const approve = useApproveKnowledge();
  const reject = useRejectKnowledge();
  const archive = useArchiveKnowledge();
  const [editing, setEditing] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  if (validId === null) return <ErrorState message="That object id is not valid." />;

  if (object.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full rounded-2xl" />
      </div>
    );
  }

  if (object.error || !object.data) {
    return (
      <ErrorState message="This knowledge object could not be loaded." onRetry={() => void object.refetch()} />
    );
  }

  const item = object.data;

  return (
    <div className="space-y-5">
      <Button
        variant="ghost"
        size="sm"
        icon={<ArrowLeft aria-hidden="true" className="h-3.5 w-3.5" />}
        onClick={() => navigate(ROUTES.knowledge)}
      >
        Back to knowledge
      </Button>

      <PageHeader
        title={item.name}
        description={item.summary ?? 'No summary recorded for this object.'}
        actions={
          <>
            <Button
              variant="secondary"
              icon={<History aria-hidden="true" className="h-4 w-4" />}
              onClick={() => setHistoryOpen(true)}
            >
              Versions
            </Button>
            <Button
              variant="secondary"
              icon={<Pencil aria-hidden="true" className="h-4 w-4" />}
              onClick={() => setEditing(true)}
            >
              Edit
            </Button>
            {item.status === 'pending_review' ? (
              <>
                <Button
                  variant="ghost"
                  icon={<X aria-hidden="true" className="h-4 w-4" />}
                  loading={reject.isPending}
                  onClick={() => reject.mutate({ id: item.id })}
                >
                  Reject
                </Button>
                <Button
                  icon={<Check aria-hidden="true" className="h-4 w-4" />}
                  loading={approve.isPending}
                  onClick={() => approve.mutate({ id: item.id })}
                >
                  Approve
                </Button>
              </>
            ) : item.status === 'approved' ? (
              <Button
                variant="ghost"
                className="text-rose-600 hover:bg-rose-50"
                icon={<Archive aria-hidden="true" className="h-4 w-4" />}
                loading={archive.isPending}
                onClick={() => archive.mutate(item.id, { onSuccess: () => navigate(ROUTES.knowledge) })}
              >
                Archive
              </Button>
            ) : null}
          </>
        }
      />

      <OkfHeader object={item} />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Attributes</CardTitle>
          </CardHeader>
          <CardBody className="pt-2">
            <AttributeTable attributes={item.payload} />
          </CardBody>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Provenance</CardTitle>
            </CardHeader>
            <CardBody className="space-y-3 pt-2 text-sm">
              <Row label="Extraction" value={item.extraction_method} />
              <Row label="Confidence" value={item.confidence === null ? '—' : formatPercent(item.confidence)} />
              <Row label="Visibility" value={VISIBILITY_LABEL[item.visibility]} />
              <Row label="Created" value={formatDateTime(item.created_at)} />
              <Row label="Updated" value={formatDateTime(item.updated_at)} />
              {item.reviewed_at ? <Row label="Reviewed" value={formatDateTime(item.reviewed_at)} /> : null}
              {item.review_note ? <Row label="Review note" value={item.review_note} /> : null}
              {item.source_document_id ? (
                <Row
                  label="Source document"
                  value={
                    <button
                      type="button"
                      className="focus-ring rounded font-medium text-indigo-700 hover:underline"
                      onClick={() => navigate(ROUTES.document(item.source_document_id as number))}
                    >
                      {document.data?.title ?? `Document ${item.source_document_id}`}
                    </button>
                  }
                />
              ) : null}
            </CardBody>
          </Card>

          {item.relations.length ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Relations</CardTitle>
              </CardHeader>
              <CardBody className="space-y-2 pt-2">
                {item.relations.map((relation) => (
                  <div key={`${relation.relation_type}-${relation.target_name}`} className="flex items-center gap-2 text-sm">
                    <Badge color="sky" size="sm">
                      {relation.relation_type}
                    </Badge>
                    <span className="text-slate-700">{relation.target_name}</span>
                  </div>
                ))}
              </CardBody>
            </Card>
          ) : null}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Source quote</CardTitle>
        </CardHeader>
        <CardBody className="pt-2">
          <SourceQuote
            quote={item.source_excerpt}
            documentId={item.source_document_id}
            documentTitle={document.data?.title ?? null}
            page={null}
          />
        </CardBody>
      </Card>

      <OkfForm open={editing} object={item} onClose={() => setEditing(false)} />

      <Drawer
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        title="Version history"
        description={item.object_key}
      >
        {versions.isPending ? (
          <div className="space-y-2">
            {[0, 1, 2].map((index) => (
              <Skeleton key={index} className="h-14 w-full rounded-xl" />
            ))}
          </div>
        ) : versions.error ? (
          <ErrorState compact message="Could not load versions." onRetry={() => void versions.refetch()} />
        ) : (
          <ol className="space-y-3">
            {(versions.data?.items ?? []).map((version) => (
              <li key={version.id} className="rounded-xl border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-slate-800">Version {version.object_version}</span>
                  <Badge color={version.is_current ? 'indigo' : 'slate'} size="sm">
                    {version.is_current ? 'current' : 'superseded'}
                  </Badge>
                </div>
                <p className="mt-0.5 text-xs text-slate-500">{formatDateTime(version.updated_at)}</p>
                <p className="mt-1 text-xs text-slate-600">
                  Status: {version.status}
                  {version.summary ? ` · ${version.summary}` : ''}
                </p>
              </li>
            ))}
          </ol>
        )}
      </Drawer>
    </div>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-2 last:border-0 last:pb-0">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      <span className="text-right text-sm text-slate-700">{value}</span>
    </div>
  );
}
