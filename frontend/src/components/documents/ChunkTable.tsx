import { FileStack } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { TD, TH, THead, TR, TableWrap, TBody } from '@/components/ui/Table';
import { useDocumentChunksQuery } from '@/hooks/useDocuments';
import { formatNumber } from '@/lib/format';

const PAGE_SIZE = 20;

export function ChunkTable({ documentId }: { documentId: number }) {
  const [page, setPage] = useState(1);
  const query = useDocumentChunksQuery(documentId, page, PAGE_SIZE);
  const data = query.data;
  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  if (query.isPending) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white">
        <SkeletonTable rows={5} />
      </div>
    );
  }

  if (query.error) {
    return (
      <ErrorState message="Could not load the chunks for this document." onRetry={() => void query.refetch()} />
    );
  }

  if (!data?.items.length) {
    return (
      <EmptyState
        icon={<FileStack aria-hidden="true" className="h-5 w-5" />}
        title="No chunks yet"
        hint="Chunks appear once chunking completes for the current version."
      />
    );
  }

  return (
    <div className="space-y-3">
      <TableWrap className="rounded-2xl border border-slate-200 bg-white">
        <THead>
          <TH className="w-16">#</TH>
          <TH className="w-20">Page</TH>
          <TH>Section</TH>
          <TH className="w-24">Tokens</TH>
          <TH>Preview</TH>
        </THead>
        <TBody>
          {data.items.map((chunk) => (
            <TR key={chunk.id}>
              <TD className="font-mono text-xs tabular-nums text-slate-500">{chunk.chunk_index}</TD>
              <TD className="tabular-nums text-slate-500">{chunk.page_number ?? '—'}</TD>
              <TD className="max-w-[180px] truncate text-slate-700" title={chunk.section_title ?? undefined}>
                {chunk.section_title ?? '—'}
              </TD>
              <TD className="tabular-nums text-slate-500">{chunk.token_count ?? '—'}</TD>
              <TD>
                <p className="line-clamp-2 text-xs leading-5 text-slate-600" title={chunk.text}>
                  {chunk.text}
                </p>
                <Badge color="slate" size="sm" className="mt-1">
                  {chunk.strategy}
                </Badge>
              </TD>
            </TR>
          ))}
        </TBody>
      </TableWrap>

      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-slate-500">
          Showing {data.items.length} of {formatNumber(data.total)} chunks
        </p>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            Previous
          </Button>
          <span className="text-xs tabular-nums text-slate-500">
            Page {page} / {pageCount}
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= pageCount}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
