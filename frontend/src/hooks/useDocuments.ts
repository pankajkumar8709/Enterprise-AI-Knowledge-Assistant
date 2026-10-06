import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, apiErrorMessage, downloadFile } from '@/lib/api';
import { MAX_UPLOAD_BYTES, queryKeys } from '@/lib/constants';
import { toast } from '@/store/uiStore';
import type { DocumentDto, Paginated, Visibility } from '@/types/api';
import type {
  ChunkPageDto,
  DocumentStatusDto,
  DocumentTextDto,
  DocumentVersionDto,
} from '@/types/domain';

/**
 * The Documents page filters and paginates client-side: `GET /documents` only
 * accepts `page`/`page_size` (no `status`/`q`/`visibility` params), so the page
 * pulls the first 100 rows once and filters them locally.
 */
export const DOCUMENT_FETCH_LIMIT = 100;

export function useDocumentsQuery(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.documents({ scope: 'all' }),
    queryFn: async () => {
      const { data } = await api.get<Paginated<DocumentDto>>('/documents', {
        params: { page: 1, page_size: DOCUMENT_FETCH_LIMIT },
      });
      return data;
    },
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    ...(options?.enabled === undefined ? {} : { enabled: options.enabled }),
  });
}

export function useDocumentQuery(id: number | null) {
  return useQuery({
    queryKey: queryKeys.document(String(id)),
    queryFn: async () => {
      const { data } = await api.get<DocumentDto>(`/documents/${id}`);
      return data;
    },
    enabled: id !== null && Number.isFinite(id),
    staleTime: 30_000,
  });
}

/** `GET /documents/{id}/status`, polled every 3 s while the document is processing. */
export function useDocumentStatus(id: number | null, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.documentStatus(String(id)),
    queryFn: async () => {
      const { data } = await api.get<DocumentStatusDto>(`/documents/${id}/status`);
      return data;
    },
    enabled: (options?.enabled ?? true) && id !== null && Number.isFinite(id),
    staleTime: 1_000,
    refetchInterval: (query) => (query.state.data?.status === 'processing' ? 3_000 : false),
  });
}

export function useDocumentVersionsQuery(id: number | null) {
  return useQuery({
    queryKey: queryKeys.documentVersions(String(id)),
    queryFn: async () => {
      const { data } = await api.get<DocumentVersionDto[]>(`/documents/${id}/versions`);
      return data;
    },
    enabled: id !== null && Number.isFinite(id),
    staleTime: 30_000,
  });
}

export function useDocumentTextQuery(id: number | null) {
  return useQuery({
    queryKey: queryKeys.documentText(String(id)),
    queryFn: async () => {
      const { data } = await api.get<DocumentTextDto>(`/documents/${id}/extracted-text`);
      return data;
    },
    enabled: id !== null && Number.isFinite(id),
    staleTime: 30_000,
  });
}

export function useDocumentChunksQuery(id: number | null, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: queryKeys.documentChunks(String(id), page),
    queryFn: async () => {
      const { data } = await api.get<ChunkPageDto>(`/documents/${id}/chunks/preview`, {
        params: { page, page_size: pageSize },
      });
      return data;
    },
    enabled: id !== null && Number.isFinite(id),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
}

export interface UploadDocumentInput {
  file: File;
  title: string;
  visibility: Visibility;
  department_ids: number[];
}

function useRefreshDocuments() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: ['documents'] });
    void queryClient.invalidateQueries({ queryKey: ['document'] });
    void queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
  };
}

/** `POST /documents` (multipart; `title` is required by the API). */
export function useUploadDocument() {
  const refresh = useRefreshDocuments();

  return useMutation({
    mutationFn: async (input: UploadDocumentInput) => {
      const form = new FormData();
      form.append('title', input.title);
      form.append('file', input.file);
      form.append('visibility', input.visibility);
      for (const id of input.department_ids) form.append('department_ids', String(id));
      const { data } = await api.post<DocumentDto>('/documents', form);
      return data;
    },
    onSuccess: (document) => {
      refresh();
      toast.success('Document uploaded', `${document.title} is now processing.`);
    },
    onError: (error) => {
      toast.error('Upload failed', apiErrorMessage(error));
    },
  });
}

/** `PUT /documents/{id}/file` — upload a new version and re-run ingestion. */
export function useUploadNewVersion() {
  const refresh = useRefreshDocuments();

  return useMutation({
    mutationFn: async (input: { id: number; file: File; note?: string }) => {
      const form = new FormData();
      form.append('file', input.file);
      if (input.note) form.append('note', input.note);
      const { data } = await api.put<DocumentDto>(`/documents/${input.id}/file`, form);
      return data;
    },
    onSuccess: () => {
      refresh();
      toast.success('New version uploaded', 'Processing restarted for this document.');
    },
    onError: (error) => {
      toast.error('Could not upload the new version', apiErrorMessage(error));
    },
  });
}

/** `PATCH /documents/{id}` — metadata + ACL; ACL changes propagate to chunks/facts. */
export function useUpdateDocument(id: number) {
  const refresh = useRefreshDocuments();

  return useMutation({
    mutationFn: async (input: { title?: string; visibility?: Visibility; department_ids?: number[] }) => {
      const { data } = await api.patch<DocumentDto>(`/documents/${id}`, input);
      return data;
    },
    onSuccess: () => {
      refresh();
      toast.success('Document updated');
    },
    onError: (error) => {
      toast.error('Update failed', apiErrorMessage(error));
    },
  });
}

export function useDeleteDocument() {
  const refresh = useRefreshDocuments();

  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/documents/${id}`);
      return id;
    },
    onSuccess: () => {
      refresh();
      toast.success('Document deleted');
    },
    onError: (error) => {
      toast.error('Delete failed', apiErrorMessage(error));
    },
  });
}

export function useReprocessDocument() {
  const refresh = useRefreshDocuments();

  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.post<DocumentDto>(`/documents/${id}/reprocess`);
      return data;
    },
    onSuccess: () => {
      refresh();
      toast.success('Reprocessing started');
    },
    onError: (error) => {
      toast.error('Could not reprocess', apiErrorMessage(error));
    },
  });
}

/** Streams a protected file through the authenticated client. */
export function useDownloadDocument() {
  return useMutation({
    mutationFn: async (document: { id: number; source_name: string }) => {
      await downloadFile(`/documents/${document.id}/download`, document.source_name);
    },
    onError: (error) => {
      toast.error('Download failed', apiErrorMessage(error));
    },
  });
}

/** Pre-flight check so obviously invalid files never reach the API. */
export function validateUploadFile(file: File, accepted: readonly string[]): string | null {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (!accepted.includes(ext)) {
    return `Unsupported file type ".${ext}". Allowed: ${accepted.join(', ')}.`;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `File is larger than ${Math.round(MAX_UPLOAD_BYTES / (1024 * 1024))} MB.`;
  }
  if (file.size === 0) return 'The selected file is empty.';
  return null;
}
