import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, apiErrorMessage } from '@/lib/api';
import { queryKeys } from '@/lib/constants';
import { toast } from '@/store/uiStore';
import type { OkfObjectDto, OkfStatus, OkfType, Visibility } from '@/types/api';
import type { KnowledgePage } from '@/types/domain';

/** `GET /knowledge` only filters by `object_type`/`document_id`, so the page pulls up to 100 current objects and filters status/search locally. */
export const KNOWLEDGE_FETCH_LIMIT = 100;

export function useKnowledgeQuery(options?: { object_type?: OkfType | ''; document_id?: number }) {
  const object_type = options?.object_type ?? '';
  const document_id = options?.document_id;

  return useQuery({
    queryKey: queryKeys.knowledge({ object_type, document_id: document_id ?? null }),
    queryFn: async () => {
      const { data } = await api.get<KnowledgePage>('/knowledge', {
        params: {
          page: 1,
          page_size: KNOWLEDGE_FETCH_LIMIT,
          include_history: false,
          ...(object_type ? { object_type } : {}),
          ...(document_id ? { document_id } : {}),
        },
      });
      return data;
    },
    staleTime: 30_000,
  });
}

export function useKnowledgeItemQuery(id: number | null) {
  return useQuery({
    queryKey: queryKeys.knowledgeItem(String(id)),
    queryFn: async () => {
      const { data } = await api.get<OkfObjectDto>(`/knowledge/${id}`);
      return data;
    },
    enabled: id !== null && Number.isFinite(id),
    staleTime: 30_000,
  });
}

/** All versions of the same canonical key (history drawer). */
export function useKnowledgeVersionsQuery(id: number | null) {
  return useQuery({
    queryKey: [...queryKeys.knowledgeItem(String(id)), 'versions'],
    queryFn: async () => {
      const { data } = await api.get<KnowledgePage>(`/knowledge/${id}/versions`, {
        params: { page_size: KNOWLEDGE_FETCH_LIMIT },
      });
      return data;
    },
    enabled: id !== null && Number.isFinite(id),
    staleTime: 30_000,
  });
}

function useRefreshKnowledge() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    void queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
  };
}

export interface OkfCreateInput {
  object_type: OkfType;
  name: string;
  payload: Record<string, unknown>;
  summary?: string | null;
  visibility: Visibility;
  department_ids: number[];
}

/** `POST /knowledge` — manually authored objects are approved on creation. */
export function useCreateKnowledge() {
  const refresh = useRefreshKnowledge();
  return useMutation({
    mutationFn: async (input: OkfCreateInput) => {
      const { data } = await api.post<OkfObjectDto>('/knowledge', input);
      return data;
    },
    onSuccess: (object) => {
      refresh();
      toast.success('Knowledge object created', object.name);
    },
    onError: (error) => toast.error('Could not create the object', apiErrorMessage(error)),
  });
}

export interface OkfUpdateInput {
  name?: string;
  payload?: Record<string, unknown>;
  summary?: string | null;
  visibility?: Visibility;
  department_ids?: number[];
  /** Mandatory: the API rejects updates without a change note (spec §8). */
  change_note: string;
}

export function useUpdateKnowledge(id: number) {
  const refresh = useRefreshKnowledge();
  return useMutation({
    mutationFn: async (input: OkfUpdateInput) => {
      const { data } = await api.put<OkfObjectDto>(`/knowledge/${id}`, input);
      return data;
    },
    onSuccess: () => {
      refresh();
      toast.success('New version saved');
    },
    onError: (error) => toast.error('Update failed', apiErrorMessage(error)),
  });
}

export function useApproveKnowledge() {
  const refresh = useRefreshKnowledge();
  return useMutation({
    mutationFn: async (input: { id: number; note?: string }) => {
      const { data } = await api.post<OkfObjectDto>(`/knowledge/${input.id}/approve`, {
        note: input.note ?? null,
      });
      return data;
    },
    onSuccess: (object) => {
      refresh();
      toast.success('Approved', `${object.name} is now visible to chat.`);
    },
    onError: (error) => toast.error('Could not approve', apiErrorMessage(error)),
  });
}

export function useRejectKnowledge() {
  const refresh = useRefreshKnowledge();
  return useMutation({
    mutationFn: async (input: { id: number; note?: string }) => {
      const { data } = await api.post<OkfObjectDto>(`/knowledge/${input.id}/reject`, {
        note: input.note ?? null,
      });
      return data;
    },
    onSuccess: () => {
      refresh();
      toast.success('Rejected');
    },
    onError: (error) => toast.error('Could not reject', apiErrorMessage(error)),
  });
}

export function useBulkReviewKnowledge() {
  const refresh = useRefreshKnowledge();
  return useMutation({
    mutationFn: async (input: { ids: number[]; action: 'approve' | 'reject' }) => {
      const { data } = await api.post<{ reviewed: number; action: string }>('/knowledge/bulk-review', input);
      return data;
    },
    onSuccess: (result) => {
      refresh();
      toast.success(`${result.action === 'approve' ? 'Approved' : 'Rejected'} ${result.reviewed} objects`);
    },
    onError: (error) => toast.error('Bulk review failed', apiErrorMessage(error)),
  });
}

/** `DELETE /knowledge/{id}` archives the object (kept for audit history). */
export function useArchiveKnowledge() {
  const refresh = useRefreshKnowledge();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/knowledge/${id}`);
      return id;
    },
    onSuccess: () => {
      refresh();
      toast.success('Object archived');
    },
    onError: (error) => toast.error('Could not archive', apiErrorMessage(error)),
  });
}

/** Reviewers show the verbatim snippet; the API stores it as `source_excerpt`. */
export function knowledgeQuote(object: OkfObjectDto): string | null {
  return object.source_excerpt?.trim() || null;
}

export function knowledgeStatusCounts(items: OkfObjectDto[]): Record<OkfStatus, number> {
  const counts: Record<OkfStatus, number> = {
    pending_review: 0,
    approved: 0,
    rejected: 0,
    archived: 0,
  };
  for (const item of items) counts[item.status] += 1;
  return counts;
}
