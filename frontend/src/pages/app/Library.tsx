import { Download, FileText, Library as LibraryIcon, Search } from 'lucide-react';
import { useMemo, useState } from 'react';

import { PageHeader } from '@/components/layout/PageHeader';
import { StatusBadge } from '@/components/documents/StatusBadge';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Input } from '@/components/ui/Input';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDebounce } from '@/hooks/useDebounce';
import { useDocumentsQuery, useDownloadDocument } from '@/hooks/useDocuments';
import { formatBytes, formatDateTime, pluralize } from '@/lib/format';

function FileKindIcon({ extension }: { extension: string }) {
  const tone =
    extension === 'pdf'
      ? 'bg-rose-50 text-rose-600'
      : extension === 'docx'
        ? 'bg-sky-50 text-sky-600'
        : extension === 'pptx'
          ? 'bg-amber-50 text-amber-600'
          : 'bg-slate-100 text-slate-500';
  return (
    <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${tone}`}>
      <FileText aria-hidden="true" className="h-5 w-5" />
    </span>
  );
}

/** `/app/documents` — read-only list of everything the signed-in user may see. */
export function LibraryPage() {
  const documents = useDocumentsQuery();
  const download = useDownloadDocument();
  const [search, setSearch] = useState('');
  const debounced = useDebounce(search, 250);

  // Every document the ACL returns is listed (§12.2.9); only ready ones are downloadable.
  const items = useMemo(() => {
    const available = documents.data?.items ?? [];
    const needle = debounced.trim().toLowerCase();
    if (!needle) return available;
    return available.filter(
      (document) =>
        document.title.toLowerCase().includes(needle) || document.source_name.toLowerCase().includes(needle),
    );
  }, [debounced, documents.data]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Library"
        description="Documents you have access to. Download anything you need, or ask about it in chat."
      />

      <div className="max-w-md">
        <label htmlFor="library-search" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
          Search
        </label>
        <Input
          id="library-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search your documents"
          icon={<Search aria-hidden="true" className="h-4 w-4" />}
        />
      </div>

      {documents.isPending ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((index) => (
            <Skeleton key={index} className="h-40 w-full rounded-2xl" />
          ))}
        </div>
      ) : documents.error ? (
        <ErrorState message="Could not load your library." onRetry={() => void documents.refetch()} />
      ) : !items.length ? (
        <Card>
          <EmptyState
            icon={<LibraryIcon aria-hidden="true" className="h-5 w-5" />}
            title={debounced ? 'No documents match your search' : 'Nothing has been shared with you yet'}
            hint={
              debounced
                ? 'Try a different title or file name.'
                : 'Documents appear here once an administrator shares them with your department.'
            }
          />
        </Card>
      ) : (
        <>
          <p className="text-xs text-slate-500">
            {items.length} {pluralize(items.length, 'document')} available
          </p>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {items.map((document) => {
              const extension = document.source_name.split('.').pop()?.toLowerCase() ?? '';
              return (
                <Card key={document.id} className="flex flex-col p-5">
                  <div className="flex items-start gap-3">
                    <FileKindIcon extension={extension} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-slate-900" title={document.title}>
                        {document.title}
                      </p>
                      <p className="truncate text-xs text-slate-500">{document.source_name}</p>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <StatusBadge status={document.status} />
                    <Badge color="slate" size="sm">
                      {formatBytes(document.size_bytes)}
                    </Badge>
                    {document.visibility === 'department' ? (
                      <Badge color="sky" size="sm">
                        department
                      </Badge>
                    ) : null}
                  </div>

                  <p className="mt-2 text-xs text-slate-500">Updated {formatDateTime(document.updated_at)}</p>

                  <div className="mt-4 flex-1" />
                  <Button
                    variant="secondary"
                    size="sm"
                    block
                    disabled={document.status !== 'ready'}
                    icon={<Download aria-hidden="true" className="h-3.5 w-3.5" />}
                    loading={download.isPending && download.variables?.id === document.id}
                    onClick={() => download.mutate({ id: document.id, source_name: document.source_name })}
                  >
                    {document.status === 'ready' ? 'Download' : 'Available once ready'}
                  </Button>
                </Card>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
