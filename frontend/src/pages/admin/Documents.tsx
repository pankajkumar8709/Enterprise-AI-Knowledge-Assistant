import { Search, Upload } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { DocumentTable } from '@/components/documents/DocumentTable';
import { UploadModal } from '@/components/documents/UploadModal';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { useDebounce } from '@/hooks/useDebounce';
import {
  DOCUMENT_FETCH_LIMIT,
  useDeleteDocument,
  useDocumentsQuery,
  useDownloadDocument,
  useReprocessDocument,
  useUploadNewVersion,
} from '@/hooks/useDocuments';
import { ROUTES, STATUS_FILTER_OPTIONS, VISIBILITY_FILTER_OPTIONS } from '@/lib/constants';
import { formatNumber, pluralize } from '@/lib/format';
import type { DocStatus, DocumentDto, Visibility } from '@/types/api';

const PAGE_SIZE = 20;

export function DocumentsPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const documents = useDocumentsQuery();
  const deleteDocument = useDeleteDocument();
  const reprocess = useReprocessDocument();
  const uploadVersion = useUploadNewVersion();
  const download = useDownloadDocument();

  const [search, setSearch] = useState(params.get('q') ?? '');
  const debouncedSearch = useDebounce(search, 300);
  const status = (params.get('status') ?? '') as DocStatus | '';
  const visibility = (params.get('visibility') ?? '') as Visibility | '';
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1);

  const [uploadOpen, setUploadOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<DocumentDto | null>(null);
  const [versionTarget, setVersionTarget] = useState<DocumentDto | null>(null);
  const [versionFile, setVersionFile] = useState<File | null>(null);
  const [versionNote, setVersionNote] = useState('');
  const [versionError, setVersionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  // Keep the search box and the URL in step so filters are shareable.
  useEffect(() => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (debouncedSearch) next.set('q', debouncedSearch);
        else next.delete('q');
        next.delete('page');
        return next;
      },
      { replace: true },
    );
  }, [debouncedSearch, setParams]);

  const filtered = useMemo(() => {
    const items = documents.data?.items ?? [];
    const needle = debouncedSearch.trim().toLowerCase();
    return items.filter((document) => {
      if (status && document.status !== status) return false;
      if (visibility && document.visibility !== visibility) return false;
      if (!needle) return true;
      return (
        document.title.toLowerCase().includes(needle) ||
        document.source_name.toLowerCase().includes(needle)
      );
    });
  }, [debouncedSearch, documents.data, status, visibility]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visible = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const truncatedCorpus = (documents.data?.total ?? 0) > DOCUMENT_FETCH_LIMIT;

  function updateParam(key: string, value: string): void {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set(key, value);
        else next.delete(key);
        next.delete('page');
        return next;
      },
      { replace: true },
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Documents"
        description="Upload source material, watch ingestion, and manage what each department can see."
        actions={
          <Button icon={<Upload aria-hidden="true" className="h-4 w-4" />} onClick={() => setUploadOpen(true)}>
            Upload document
          </Button>
        }
      />

      <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label htmlFor="doc-search" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
            Search
          </label>
          <Input
            id="doc-search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by title or file name"
            icon={<Search aria-hidden="true" className="h-4 w-4" />}
          />
        </div>
        <div className="sm:w-44">
          <label htmlFor="doc-status" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
            Status
          </label>
          <Select id="doc-status" value={status} onChange={(event) => updateParam('status', event.target.value)}>
            {STATUS_FILTER_OPTIONS.map((option) => (
              <option key={option.label} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="sm:w-52">
          <label
            htmlFor="doc-visibility"
            className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500"
          >
            Visibility
          </label>
          <Select
            id="doc-visibility"
            value={visibility}
            onChange={(event) => updateParam('visibility', event.target.value)}
          >
            {VISIBILITY_FILTER_OPTIONS.map((option) => (
              <option key={option.label} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <DocumentTable
        documents={visible}
        loading={documents.isPending}
        error={documents.error}
        onRetry={() => void documents.refetch()}
        busyId={busyId}
        onView={(document) => navigate(ROUTES.document(document.id))}
        onNewVersion={(document) => {
          setVersionTarget(document);
          setVersionFile(null);
          setVersionNote('');
          setVersionError(null);
        }}
        onReprocess={(document) => {
          setBusyId(document.id);
          reprocess.mutate(document.id, { onSettled: () => setBusyId(null) });
        }}
        onDelete={(document) => setPendingDelete(document)}
        onDownload={(document) => download.mutate({ id: document.id, source_name: document.source_name })}
        emptyAction={
          <Button icon={<Upload aria-hidden="true" className="h-4 w-4" />} onClick={() => setUploadOpen(true)}>
            Upload document
          </Button>
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-500">
          {formatNumber(filtered.length)} {pluralize(filtered.length, 'document')}
          {status || visibility || debouncedSearch ? ' matching the current filters' : ''}
          {truncatedCorpus ? ` · filters apply to the ${DOCUMENT_FETCH_LIMIT} most recent` : ''}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={currentPage <= 1}
            onClick={() => updateParam('page', String(currentPage - 1))}
          >
            Previous
          </Button>
          <span className="text-xs tabular-nums text-slate-500">
            Page {currentPage} / {pageCount}
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={currentPage >= pageCount}
            onClick={() => updateParam('page', String(currentPage + 1))}
          >
            Next
          </Button>
        </div>
      </div>

      <UploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} />

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete document"
        message={`${pendingDelete?.title ?? 'This document'} and all of its chunks, versions and derived facts will be removed. This cannot be undone.`}
        confirmLabel="Delete document"
        loading={deleteDocument.isPending}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) deleteDocument.mutate(pendingDelete.id);
          setPendingDelete(null);
        }}
      />

      <Modal
        open={versionTarget !== null}
        onClose={() => setVersionTarget(null)}
        title="Upload a new version"
        description={`Replaces the file for "${versionTarget?.title ?? ''}" and re-runs ingestion.`}
        dismissible={!uploadVersion.isPending}
        footer={
          <>
            <Button variant="secondary" onClick={() => setVersionTarget(null)} disabled={uploadVersion.isPending}>
              Cancel
            </Button>
            <Button
              loading={uploadVersion.isPending}
              onClick={() => {
                const target = versionTarget;
                if (!target) return;
                if (!versionFile) {
                  setVersionError('Choose a replacement file.');
                  return;
                }
                uploadVersion.mutate(
                  { id: target.id, file: versionFile, note: versionNote.trim() },
                  { onSuccess: () => setVersionTarget(null) },
                );
              }}
            >
              Upload version
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label htmlFor="version-file" className="mb-1.5 block text-sm font-medium text-slate-700">
              Replacement file
            </label>
            <input
              id="version-file"
              type="file"
              accept=".pdf,.docx,.pptx,.txt,.md"
              onChange={(event) => {
                setVersionFile(event.target.files?.[0] ?? null);
                setVersionError(null);
              }}
              className="focus-ring block w-full cursor-pointer rounded-xl border border-slate-300 bg-white p-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-medium"
            />
            {versionError ? (
              <p role="alert" className="mt-1.5 text-xs font-medium text-rose-600">
                {versionError}
              </p>
            ) : null}
          </div>
          <div>
            <label htmlFor="version-note" className="mb-1.5 block text-sm font-medium text-slate-700">
              Version note (optional)
            </label>
            <Input
              id="version-note"
              value={versionNote}
              placeholder="Updated leave entitlement for 2026"
              onChange={(event) => setVersionNote(event.target.value)}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
