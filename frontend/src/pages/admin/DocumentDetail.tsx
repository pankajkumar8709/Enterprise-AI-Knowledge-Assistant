import { ArrowLeft, Download, FileText, Pencil, RotateCw, Upload } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ChunkTable } from '@/components/documents/ChunkTable';
import { ProcessingStepper } from '@/components/documents/ProcessingStepper';
import { StatusBadge } from '@/components/documents/StatusBadge';
import { VersionList } from '@/components/documents/VersionList';
import { TypeBadge } from '@/components/knowledge/TypeBadge';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { FormField, Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { TD, TH, THead, TR, TableWrap, TBody } from '@/components/ui/Table';
import { TabPanel, Tabs } from '@/components/ui/Tabs';
import { useDepartmentsQuery } from '@/hooks/useAdmin';
import {
  useDeleteDocument,
  useDocumentQuery,
  useDocumentStatus,
  useDocumentTextQuery,
  useDocumentVersionsQuery,
  useDownloadDocument,
  useReprocessDocument,
  useUpdateDocument,
  useUploadNewVersion,
} from '@/hooks/useDocuments';
import { useKnowledgeQuery } from '@/hooks/useKnowledge';
import { ROUTES, VISIBILITY_LABEL } from '@/lib/constants';
import { formatBytes, formatDateTime, formatNumber, formatPercent, truncate } from '@/lib/format';
import type { Visibility } from '@/types/api';

type TabId = 'overview' | 'text' | 'chunks' | 'knowledge';

const TAB_ITEMS = [
  { id: 'overview' as const, label: 'Overview' },
  { id: 'text' as const, label: 'Extracted text' },
  { id: 'chunks' as const, label: 'Chunks' },
  { id: 'knowledge' as const, label: 'Knowledge' },
];

export function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();
  const id = documentId ? Number(documentId) : NaN;
  const validId = Number.isFinite(id) ? id : null;

  const [tab, setTab] = useState<TabId>('overview');
  const document = useDocumentQuery(validId);
  const status = useDocumentStatus(validId, { enabled: document.data?.status === 'processing' });
  const versions = useDocumentVersionsQuery(validId);
  const text = useDocumentTextQuery(validId);
  const knowledge = useKnowledgeQuery(validId ? { document_id: validId } : undefined);
  const departments = useDepartmentsQuery();
  const reprocess = useReprocessDocument();
  const remove = useDeleteDocument();
  const download = useDownloadDocument();
  const uploadVersion = useUploadNewVersion();
  const update = useUpdateDocument(validId ?? 0);

  const [versionOpen, setVersionOpen] = useState(false);
  const [versionFile, setVersionFile] = useState<File | null>(null);
  const [versionNote, setVersionNote] = useState('');
  const [aclOpen, setAclOpen] = useState(false);
  const [aclTitle, setAclTitle] = useState('');
  const [aclVisibility, setAclVisibility] = useState<Visibility>('all');
  const [aclDepartments, setAclDepartments] = useState<number[]>([]);
  const [textMode, setTextMode] = useState<'clean' | 'raw'>('clean');
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (validId === null) {
    return <ErrorState message="That document id is not valid." />;
  }

  if (document.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (document.error || !document.data) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" icon={<ArrowLeft aria-hidden="true" className="h-3.5 w-3.5" />} onClick={() => navigate(ROUTES.documents)}>
          Back to documents
        </Button>
        <ErrorState message="This document could not be loaded." onRetry={() => void document.refetch()} />
      </div>
    );
  }

  const doc = document.data;
  const liveStatus = status.data?.status ?? doc.status;
  const liveStage = status.data?.stage ?? null;
  const knowledgeItems = knowledge.data?.items ?? [];

  return (
    <div className="space-y-5">
      <Button
        variant="ghost"
        size="sm"
        icon={<ArrowLeft aria-hidden="true" className="h-3.5 w-3.5" />}
        onClick={() => navigate(ROUTES.documents)}
      >
        Back to documents
      </Button>

      <PageHeader
        title={doc.title}
        description={`${doc.source_name} · ${formatBytes(doc.size_bytes)} · version ${doc.version}`}
        actions={
          <>
            <Button
              variant="secondary"
              icon={<RotateCw aria-hidden="true" className="h-4 w-4" />}
              loading={reprocess.isPending}
              onClick={() => reprocess.mutate(doc.id)}
            >
              Reprocess
            </Button>
            <Button
              variant="secondary"
              icon={<Upload aria-hidden="true" className="h-4 w-4" />}
              onClick={() => setVersionOpen(true)}
            >
              New version
            </Button>
            <Button
              icon={<Download aria-hidden="true" className="h-4 w-4" />}
              onClick={() => download.mutate({ id: doc.id, source_name: doc.source_name })}
            >
              Download
            </Button>
          </>
        }
      />

      <Card className="p-5">
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={liveStatus} />
          <ProcessingStepper stage={liveStage} status={liveStatus} variant="full" />
        </div>
        {liveStatus === 'failed' ? (
          <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {status.data?.error_message ?? doc.chunking_error ?? doc.extraction_error ?? 'Processing failed.'}
          </p>
        ) : null}
      </Card>

      <Tabs items={TAB_ITEMS} value={tab} onChange={setTab} aria-label="Document sections" />

      <TabPanel id="overview" active={tab === 'overview'}>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Metadata</CardTitle>
            </CardHeader>
            <CardBody className="pt-2">
              <dl className="divide-y divide-slate-100">
                <MetaRow label="Document id" value={<span className="font-mono text-xs">{doc.id}</span>} />
                <MetaRow label="File" value={<span className="font-mono text-xs">{doc.source_name}</span>} />
                <MetaRow label="Content type" value={doc.content_type} />
                <MetaRow label="Size" value={formatBytes(doc.size_bytes)} />
                <MetaRow label="Chunks" value={formatNumber(doc.chunk_count)} />
                <MetaRow label="OCR used" value={doc.extraction_ocr_used ? 'Yes' : 'No'} />
                <MetaRow label="Extracted characters" value={formatNumber(doc.extracted_char_count ?? 0)} />
                <MetaRow label="Uploaded" value={formatDateTime(doc.created_at)} />
                <MetaRow label="Updated" value={formatDateTime(doc.updated_at)} />
                <MetaRow
                  label="SHA-256"
                  value={<span className="font-mono text-xs">{truncate(doc.sha256 ?? '—', 24)}</span>}
                />
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Access control</CardTitle>
                <p className="mt-0.5 text-sm text-slate-500">Applies to every chunk and fact from this document.</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                icon={<Pencil aria-hidden="true" className="h-3.5 w-3.5" />}
                onClick={() => {
                  setAclTitle(doc.title);
                  setAclVisibility(doc.visibility);
                  setAclDepartments(doc.department_ids);
                  setAclOpen(true);
                }}
              >
                Edit
              </Button>
            </CardHeader>
            <CardBody className="space-y-4 pt-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge color={doc.visibility === 'admin_only' ? 'amber' : 'slate'}>
                  {VISIBILITY_LABEL[doc.visibility]}
                </Badge>
                {doc.department_ids.length
                  ? doc.department_ids.map((departmentId) => {
                      const department = departments.data?.find((item) => item.id === departmentId);
                      return (
                        <Badge key={departmentId} color="sky" size="sm">
                          {department?.name ?? `Department ${departmentId}`}
                        </Badge>
                      );
                    })
                  : null}
              </div>
              <div>
                <p className="mb-2 text-sm font-semibold text-slate-700">Version history</p>
                <VersionList
                  versions={versions.data}
                  loading={versions.isPending}
                  error={versions.error}
                  onRetry={() => void versions.refetch()}
                  currentVersion={doc.version}
                />
              </div>
            </CardBody>
          </Card>
        </div>
      </TabPanel>

      <TabPanel id="text" active={tab === 'text'}>
        <Card>
          <CardHeader>
            <CardTitle>Extracted text</CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant={textMode === 'clean' ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setTextMode('clean')}
              >
                Clean
              </Button>
              <Button variant={textMode === 'raw' ? 'secondary' : 'ghost'} size="sm" onClick={() => setTextMode('raw')}>
                Raw
              </Button>
            </div>
          </CardHeader>
          <CardBody className="pt-2">
            {text.isPending ? (
              <div className="space-y-2">
                {[0, 1, 2, 3, 4, 5].map((index) => (
                  <Skeleton key={index} className="h-3.5 w-full" />
                ))}
              </div>
            ) : text.error ? (
              <ErrorState compact message="Could not load the extracted text." onRetry={() => void text.refetch()} />
            ) : !(textMode === 'clean' ? text.data?.clean_text : text.data?.raw_text) ? (
              <EmptyState
                icon={<FileText aria-hidden="true" className="h-5 w-5" />}
                title="No extracted text yet"
                hint="Text appears after the extraction stage completes."
              />
            ) : (
              <pre className="thin-scrollbar max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50 p-4 font-sans text-sm leading-6 text-slate-700">
                {textMode === 'clean' ? text.data?.clean_text : text.data?.raw_text}
              </pre>
            )}
          </CardBody>
        </Card>
      </TabPanel>

      <TabPanel id="chunks" active={tab === 'chunks'}>
        <ChunkTable documentId={doc.id} />
      </TabPanel>

      <TabPanel id="knowledge" active={tab === 'knowledge'}>
        {knowledge.isPending ? (
          <div className="space-y-2">
            {[0, 1, 2].map((index) => (
              <Skeleton key={index} className="h-12 w-full rounded-xl" />
            ))}
          </div>
        ) : knowledge.error ? (
          <ErrorState message="Could not load knowledge objects." onRetry={() => void knowledge.refetch()} />
        ) : !knowledgeItems.length ? (
          <EmptyState
            icon={<FileText aria-hidden="true" className="h-5 w-5" />}
            title="No facts extracted"
            hint="Facts appear once the extraction stage finds structured knowledge in this document."
          />
        ) : (
          <TableWrap className="rounded-2xl border border-slate-200 bg-white">
            <THead>
              <TH>Type</TH>
              <TH>Name</TH>
              <TH>Status</TH>
              <TH className="text-right">Confidence</TH>
              <TH className="text-right">Version</TH>
            </THead>
            <TBody>
              {knowledgeItems.map((object) => (
                <TR key={object.id}>
                  <TD>
                    <TypeBadge type={object.object_type} size="sm" />
                  </TD>
                  <TD>
                    <Link
                      to={ROUTES.knowledgeDetail(object.id)}
                      className="focus-ring rounded font-medium text-slate-800 hover:text-indigo-700"
                    >
                      {object.name}
                    </Link>
                    <span className="block font-mono text-[11px] text-slate-400">{object.object_key}</span>
                  </TD>
                  <TD>
                    <Badge
                      color={
                        object.status === 'approved'
                          ? 'emerald'
                          : object.status === 'pending_review'
                            ? 'amber'
                            : object.status === 'rejected'
                              ? 'rose'
                              : 'slate'
                      }
                      size="sm"
                    >
                      {object.status}
                    </Badge>
                  </TD>
                  <TD className="text-right tabular-nums text-slate-600">
                    {object.confidence === null ? '—' : formatPercent(object.confidence)}
                  </TD>
                  <TD className="text-right tabular-nums text-slate-500">{object.object_version}</TD>
                </TR>
              ))}
            </TBody>
          </TableWrap>
        )}
      </TabPanel>

      <Modal
        open={versionOpen}
        onClose={() => setVersionOpen(false)}
        title="Upload a new version"
        description={`Replaces the file for "${doc.title}" and re-runs ingestion.`}
        dismissible={!uploadVersion.isPending}
        footer={
          <>
            <Button variant="secondary" onClick={() => setVersionOpen(false)} disabled={uploadVersion.isPending}>
              Cancel
            </Button>
            <Button
              loading={uploadVersion.isPending}
              onClick={() => {
                if (!versionFile) return;
                uploadVersion.mutate(
                  { id: doc.id, file: versionFile, note: versionNote.trim() },
                  { onSuccess: () => setVersionOpen(false) },
                );
              }}
            >
              Upload version
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormField label="Replacement file" required htmlFor="detail-version-file">
            <input
              id="detail-version-file"
              type="file"
              accept=".pdf,.docx,.pptx,.txt,.md"
              onChange={(event) => setVersionFile(event.target.files?.[0] ?? null)}
              className="focus-ring block w-full cursor-pointer rounded-xl border border-slate-300 bg-white p-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-medium"
            />
          </FormField>
          <FormField label="Version note" hint="Optional context for the audit trail." htmlFor="detail-version-note">
            <Input
              id="detail-version-note"
              value={versionNote}
              onChange={(event) => setVersionNote(event.target.value)}
            />
          </FormField>
        </div>
      </Modal>

      <Modal
        open={aclOpen}
        onClose={() => setAclOpen(false)}
        title="Edit document"
        description="Changing visibility propagates to every chunk and fact derived from this document."
        dismissible={!update.isPending}
        footer={
          <>
            <Button variant="secondary" onClick={() => setAclOpen(false)} disabled={update.isPending}>
              Cancel
            </Button>
            <Button
              loading={update.isPending}
              onClick={() =>
                update.mutate(
                  {
                    title: aclTitle.trim() || doc.title,
                    visibility: aclVisibility,
                    department_ids: aclVisibility === 'department' ? aclDepartments : [],
                  },
                  { onSuccess: () => setAclOpen(false) },
                )
              }
            >
              Save changes
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormField label="Title" required htmlFor="acl-title">
            <Input id="acl-title" value={aclTitle} onChange={(event) => setAclTitle(event.target.value)} />
          </FormField>
          <FormField label="Visibility" htmlFor="acl-visibility">
            <Select
              id="acl-visibility"
              value={aclVisibility}
              onChange={(event) => setAclVisibility(event.target.value as Visibility)}
            >
              <option value="all">{VISIBILITY_LABEL.all}</option>
              <option value="department">{VISIBILITY_LABEL.department}</option>
              <option value="admin_only">{VISIBILITY_LABEL.admin_only}</option>
            </Select>
          </FormField>
          {aclVisibility === 'department' ? (
            <div className="grid max-h-36 gap-1 overflow-y-auto rounded-xl border border-slate-200 p-2 sm:grid-cols-2">
              {(departments.data ?? []).map((department) => (
                <label key={department.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    checked={aclDepartments.includes(department.id)}
                    onChange={(event) =>
                      setAclDepartments((current) =>
                        event.target.checked
                          ? [...current, department.id]
                          : current.filter((value) => value !== department.id),
                      )
                    }
                  />
                  {department.name}
                </label>
              ))}
            </div>
          ) : null}
        </div>
      </Modal>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete document"
        message={`"${doc.title}" and all of its chunks, versions and derived facts will be removed. This cannot be undone.`}
        confirmLabel="Delete document"
        loading={remove.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => {
          remove.mutate(doc.id, { onSuccess: () => navigate(ROUTES.documents) });
          setConfirmDelete(false);
        }}
      />

      <div className="flex justify-end">
        <Button
          variant="ghost"
          className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
          onClick={() => setConfirmDelete(true)}
        >
          Delete document
        </Button>
      </div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-right text-sm text-slate-700">{value}</dd>
    </div>
  );
}
