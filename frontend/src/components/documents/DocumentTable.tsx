import { useQueryClient } from '@tanstack/react-query';
import { Download, Eye, FileText, RotateCw, Trash2, Upload } from 'lucide-react';
import { useEffect, type ReactNode } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { TD, TH, THead, TR, TableWrap, TBody } from '@/components/ui/Table';
import { Tooltip } from '@/components/ui/Tooltip';
import { useDocumentStatus } from '@/hooks/useDocuments';
import { VISIBILITY_LABEL } from '@/lib/constants';
import { formatDateTime, formatNumber } from '@/lib/format';
import type { DocumentDto } from '@/types/api';

import { ProcessingStepper } from './ProcessingStepper';
import { StatusBadge } from './StatusBadge';

export interface DocumentTableProps {
  documents: DocumentDto[];
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  onView: (document: DocumentDto) => void;
  onNewVersion: (document: DocumentDto) => void;
  onReprocess: (document: DocumentDto) => void;
  onDelete: (document: DocumentDto) => void;
  onDownload: (document: DocumentDto) => void;
  emptyAction?: ReactNode;
  busyId?: number | null;
}

/** Live status cell: polls `GET /documents/{id}/status` only while processing. */
function DocumentStatusCell({ document }: { document: DocumentDto }) {
  const queryClient = useQueryClient();
  const polling = document.status === 'processing';
  const status = useDocumentStatus(document.id, { enabled: polling });
  const current = status.data?.status ?? document.status;
  const stage = status.data?.stage ?? null;

  useEffect(() => {
    if (polling && status.data && status.data.status !== 'processing') {
      void queryClient.invalidateQueries({ queryKey: ['documents'] });
    }
  }, [polling, queryClient, status.data]);

  const errorMessage = status.data?.error_message ?? document.chunking_error ?? document.extraction_error ?? null;

  return (
    <div className="space-y-1.5">
      <StatusBadge status={current} />
      {current === 'processing' ? <ProcessingStepper stage={stage} status="processing" /> : null}
      {current === 'failed' && errorMessage ? (
        <p className="max-w-[220px] text-xs text-rose-700" title={errorMessage}>
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}

export function DocumentTable({
  documents,
  loading,
  error,
  onRetry,
  onView,
  onNewVersion,
  onReprocess,
  onDelete,
  onDownload,
  emptyAction,
  busyId = null,
}: DocumentTableProps) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white">
        <SkeletonTable rows={6} cols={5} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white">
        <ErrorState message="Could not load documents." onRetry={onRetry} />
      </div>
    );
  }

  if (!documents.length) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white">
        <EmptyState
          icon={<FileText aria-hidden="true" className="h-5 w-5" />}
          title="No documents found"
          hint="Upload a policy, handbook or product sheet to build the knowledge base."
          action={emptyAction}
        />
      </div>
    );
  }

  return (
    <TableWrap className="rounded-2xl border border-slate-200 bg-white">
      <THead>
        <TH>Document</TH>
        <TH>Status</TH>
        <TH>Visibility</TH>
        <TH className="text-right">Chunks</TH>
        <TH className="text-right">Ver.</TH>
        <TH>Uploaded</TH>
        <TH className="text-right">Actions</TH>
      </THead>
      <TBody>
        {documents.map((document) => (
          <TR key={document.id}>
            <TD>
              <button
                type="button"
                onClick={() => onView(document)}
                className="focus-ring rounded text-left"
              >
                <span className="block font-medium text-slate-900 hover:text-indigo-700">{document.title}</span>
                <span className="block font-mono text-[11px] text-slate-500">{document.source_name}</span>
              </button>
            </TD>
            <TD>
              <DocumentStatusCell document={document} />
            </TD>
            <TD>
              <Badge color={document.visibility === 'admin_only' ? 'amber' : 'slate'}>
                {VISIBILITY_LABEL[document.visibility] ?? document.visibility}
              </Badge>
              {document.visibility === 'department' && document.department_ids.length ? (
                <p className="mt-1 text-[11px] text-slate-500">
                  {document.department_ids.length} department{document.department_ids.length === 1 ? '' : 's'}
                </p>
              ) : null}
            </TD>
            <TD className="text-right tabular-nums">{formatNumber(document.chunk_count)}</TD>
            <TD className="text-right tabular-nums text-slate-500">{document.version}</TD>
            <TD className="whitespace-nowrap text-slate-500">{formatDateTime(document.created_at)}</TD>
            <TD>
              <div className="flex items-center justify-end gap-1">
                <Tooltip content="View details">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`View ${document.title}`}
                    onClick={() => onView(document)}
                    icon={<Eye aria-hidden="true" className="h-4 w-4" />}
                  />
                </Tooltip>
                <Tooltip content="Upload a new version">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Upload a new version of ${document.title}`}
                    onClick={() => onNewVersion(document)}
                    icon={<Upload aria-hidden="true" className="h-4 w-4" />}
                  />
                </Tooltip>
                <Tooltip content="Reprocess">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Reprocess ${document.title}`}
                    loading={busyId === document.id}
                    onClick={() => onReprocess(document)}
                    icon={<RotateCw aria-hidden="true" className="h-4 w-4" />}
                  />
                </Tooltip>
                <Tooltip content="Download">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Download ${document.title}`}
                    onClick={() => onDownload(document)}
                    icon={<Download aria-hidden="true" className="h-4 w-4" />}
                  />
                </Tooltip>
                <Tooltip content="Delete">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete ${document.title}`}
                    onClick={() => onDelete(document)}
                    icon={<Trash2 aria-hidden="true" className="h-4 w-4 text-rose-600" />}
                  />
                </Tooltip>
              </div>
            </TD>
          </TR>
        ))}
      </TBody>
    </TableWrap>
  );
}
