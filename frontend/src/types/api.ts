/**
 * API types (§13.4) aligned to the endpoints actually implemented in Phases 0–8.
 *
 * The build plan's §13.4 sketch assumes UUID ids and a few renamed fields; the
 * shipped backend uses integer primary keys and the names below. Where they
 * differ, these types follow the running API so every §12 flow works end to end.
 * See frontend/README.md for the full deviation table.
 */

export type Role = 'admin' | 'employee';
export type DocStatus = 'uploaded' | 'processing' | 'ready' | 'failed';
export type ExtractionStatus = 'pending' | 'processing' | 'ready' | 'failed';
export type ChunkingStatus = 'pending' | 'processing' | 'ready' | 'failed';
export type DocStage =
  | 'extracting'
  | 'cleaning'
  | 'chunking'
  | 'embedding'
  | 'okf_extracting'
  | 'indexing'
  | 'done';
export type Visibility = 'all' | 'department' | 'admin_only';
export type OkfType =
  | 'policy'
  | 'employee'
  | 'department'
  | 'product'
  | 'faq'
  | 'business_rule'
  | 'asset';
export type OkfStatus = 'pending_review' | 'approved' | 'rejected' | 'archived';
export type ChatRoute = 'structured' | 'document' | 'mixed';
export type ConfidenceLabel = 'high' | 'medium' | 'low';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  department_id: number | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

/** `GET /documents`, `POST /documents`, `GET /documents/{id}` → `DocumentRead`. */
export interface DocumentDto {
  id: number;
  title: string;
  source_name: string;
  stored_name: string;
  content_type: string;
  size_bytes: number;
  sha256: string | null;
  status: DocStatus;
  version: number;
  visibility: Visibility;
  department_ids: number[];
  extraction_status: ExtractionStatus;
  extraction_error: string | null;
  extraction_ocr_used: boolean;
  extracted_char_count: number | null;
  extraction_started_at: string | null;
  extraction_completed_at: string | null;
  chunking_status: ChunkingStatus;
  chunking_error: string | null;
  chunk_count: number;
  chunking_started_at: string | null;
  chunking_completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OkfRelation {
  relation_type: string;
  target_type: OkfType | null;
  target_name: string;
  evidence: string | null;
}

/** `GET /knowledge` → `KnowledgeObjectRead`. */
export interface OkfObjectDto {
  id: number;
  object_type: OkfType;
  object_key: string;
  name: string;
  payload: Record<string, unknown>;
  relations: OkfRelation[];
  summary: string | null;
  source_excerpt: string | null;
  schema_version: number;
  object_version: number;
  is_current: boolean;
  extraction_method: string;
  source_document_id: number | null;
  status: OkfStatus;
  visibility: Visibility;
  department_ids: number[];
  confidence: number | null;
  created_by_id: number | null;
  reviewed_by_id: number | null;
  reviewed_at: string | null;
  review_note: string | null;
  created_at: string;
  updated_at: string;
}

interface SourceBase {
  ref: string;
  kind: string;
  title: string;
  score: number;
  cited: boolean;
  snippet: string | null;
}

export interface ChunkSource extends SourceBase {
  kind: 'chunk';
  chunk_id: number | null;
  document_id: number | null;
  section_title: string | null;
  page: number | null;
}

export interface OkfSource extends SourceBase {
  kind: 'okf';
  okf_object_id: number | null;
  okf_type: OkfType | null;
  facts: Record<string, unknown>;
  origin: {
    document_id?: number;
    document_title?: string;
    page?: number | null;
  } | null;
}

export type Source = ChunkSource | OkfSource;

export interface ChatAnswer {
  message_id: number;
  conversation_id: number;
  answer: string;
  answerable: boolean;
  route: ChatRoute;
  confidence: number;
  confidence_label: ConfidenceLabel;
  sources: Source[];
  latency_ms: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  answer?: ChatAnswer;
  error?: boolean;
  pending?: boolean;
}

/** Login/refresh response (`TokenResponse`). */
export interface TokenPair {
  access_token: string;
  refresh_token: string | null;
  token_type: string;
  expires_in: number | null;
  user: { id: number; email: string; full_name: string; role: string } | null;
}
