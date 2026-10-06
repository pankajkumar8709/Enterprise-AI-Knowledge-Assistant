import type {
  ChunkingStatus,
  DocumentDto,
  DocStage,
  DocStatus,
  OkfObjectDto,
  OkfStatus,
  OkfType,
  Paginated,
  Visibility,
} from './api';

/** A row in `GET /documents`. */
export type DocumentRow = DocumentDto;

/** `GET /documents/{id}/status` → `DocumentStatusRead`. */
export interface DocumentJobDto {
  id: number;
  status: string;
  attempt: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface DocumentStatusDto {
  document_id: number;
  status: DocStatus;
  stage: DocStage;
  progress_pct: number;
  error_message: string | null;
  job: DocumentJobDto | null;
}

export interface DepartmentDto {
  id: number;
  name: string;
  description: string | null;
}

/** `GET /documents/{id}/versions` → `DocumentVersionRead`. */
export interface DocumentVersionDto {
  id: number;
  version: number;
  sha256: string | null;
  size_bytes: number;
  uploaded_by_id: number | null;
  note: string | null;
  created_at: string;
}

/** `GET /documents/{id}/extracted-text`. */
export interface DocumentTextDto {
  document_id: number;
  raw_text: string | null;
  clean_text: string | null;
}

/** `GET /documents/{id}/chunks/preview` → `ChunkPreviewRead`. */
export interface ChunkDto {
  id: number;
  strategy: string;
  status: string;
  chunk_index: number;
  text: string;
  text_length: number;
  token_count: number | null;
  overlap_size: number;
  page_number: number | null;
  section_title: string | null;
  source_file_name: string;
  upload_date: string;
}

export interface ChunkPageDto {
  document_id: number;
  chunking_status: ChunkingStatus;
  strategy: string | null;
  total: number;
  page: number;
  page_size: number;
  items: ChunkDto[];
}

/** `GET /admin/audit-logs`. */
export interface AuditLogDto {
  id: number;
  user_id: number | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  metadata: Record<string, unknown> | null;
  ip: string | null;
  created_at: string;
}

/** `GET /admin/stats`. */
export interface AdminStatsDto {
  documents: { total: number; ready: number; processing: number; failed: number };
  okf: { approved: number; pending: number };
  users: number;
  queries_7d: number;
  avg_latency_ms: number;
  helpful_rate: number;
}

/** `GET /chat/conversations`. */
export interface ConversationDto {
  id: number;
  title: string | null;
  archived: boolean;
  created_at: string;
}

export interface ConversationMessageDto {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface ConversationDetailDto {
  id: number;
  title: string | null;
  archived: boolean;
  created_at: string;
  messages: ConversationMessageDto[];
}

/** `POST /search/semantic` → `SemanticSearchResult`. */
export interface SemanticHitDto {
  chunk_id: number;
  document_id: number;
  document_title: string;
  page_start: number | null;
  section_title: string | null;
  content: string;
  token_count: number | null;
  similarity: number;
  fts_rank: number;
  rrf_score: number;
}

/** `POST /search/okf` → `OKFSearchResult`. */
export interface OkfSearchHitDto {
  okf_id: number;
  object_type: string;
  name: string;
  canonical_key: string;
  attributes: Record<string, unknown>;
  score: number;
  source_document_id: number | null;
  confidence: number | null;
  via_relation: boolean;
  relation_predicate: string | null;
}

export type DocumentsPage = Paginated<DocumentRow>;
export type KnowledgePage = Paginated<OkfObjectDto>;

/** `''` (or omitted) means "no filter" for every optional field. */
export interface DocumentFilters {
  page?: number;
  page_size?: number;
  status?: DocStatus | '';
  q?: string;
  visibility?: Visibility | '';
}

/** `GET /knowledge` accepts `object_type`, not `type`. */
export interface KnowledgeFilters {
  page?: number;
  page_size?: number;
  object_type?: OkfType | '';
  status?: OkfStatus | '';
  q?: string;
  document_id?: number;
}

export interface AuditFilters {
  page?: number;
  page_size?: number;
  user_id?: number | '';
  action?: string;
  /** ISO-8601; sent as the `from`/`to` query aliases. */
  from?: string;
  to?: string;
}

/** One row of a manual knowledge-object form (spec §6.2 type attributes). */
export interface OkfFieldSpec {
  key: string;
  label: string;
  type: 'string' | 'text' | 'number' | 'array';
  required: boolean;
  placeholder?: string;
}
