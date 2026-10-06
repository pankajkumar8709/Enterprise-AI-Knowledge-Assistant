import type { ChatRoute, ConfidenceLabel, DocStage, DocStatus, OkfStatus, OkfType, Visibility } from '@/types/api';
import type { OkfFieldSpec } from '@/types/domain';

export const APP_NAME = 'Knowledge Assistant';
export const APP_TAGLINE = 'Answers grounded in your own documents and reviewed facts.';

export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
export const ACCEPTED_EXTENSIONS = ['pdf', 'docx', 'pptx', 'txt', 'md'] as const;
export const ACCEPT_ATTRIBUTE = ACCEPTED_EXTENSIONS.map((e) => `.${e}`).join(',');

export const DOC_STATUS_LABEL: Record<DocStatus, string> = {
  uploaded: 'Uploaded',
  processing: 'Processing',
  ready: 'Ready',
  failed: 'Failed',
};

/** The six ingestion stages shown in the stepper, in order. */
export const STAGE_ORDER: DocStage[] = [
  'extracting',
  'cleaning',
  'chunking',
  'embedding',
  'okf_extracting',
  'indexing',
];

export const STAGE_LABEL: Record<DocStage, string> = {
  extracting: 'Extracting',
  cleaning: 'Cleaning',
  chunking: 'Chunking',
  embedding: 'Embedding',
  okf_extracting: 'Facts',
  indexing: 'Indexing',
  done: 'Done',
};

export const VISIBILITY_LABEL: Record<Visibility, string> = {
  all: 'All employees',
  department: 'Specific departments',
  admin_only: 'Admins only',
};

export const OKF_TYPE_LABEL: Record<OkfType, string> = {
  policy: 'Policy',
  employee: 'Employee',
  department: 'Department',
  product: 'Product',
  faq: 'FAQ',
  business_rule: 'Business rule',
  asset: 'Asset',
};

export const OKF_TYPE_ORDER: OkfType[] = [
  'policy',
  'employee',
  'department',
  'product',
  'faq',
  'business_rule',
  'asset',
];

export const OKF_STATUS_LABEL: Record<OkfStatus, string> = {
  pending_review: 'Pending review',
  approved: 'Approved',
  rejected: 'Rejected',
  archived: 'Archived',
};

/** Route badge copy from §13.1: Structured → "Facts", Document → "Documents". */
export const ROUTE_LABEL: Record<ChatRoute, string> = {
  structured: 'Facts',
  document: 'Documents',
  mixed: 'Facts + Documents',
};

export const CONFIDENCE_LABEL: Record<ConfidenceLabel, string> = {
  high: 'High confidence',
  medium: 'Medium confidence',
  low: 'Low confidence',
};

/** `''` is the "no filter" sentinel for every filter select. */
export const STATUS_FILTER_OPTIONS: { value: DocStatus | ''; label: string }[] = [
  { value: '', label: 'All statuses' },
  { value: 'uploaded', label: 'Uploaded' },
  { value: 'processing', label: 'Processing' },
  { value: 'ready', label: 'Ready' },
  { value: 'failed', label: 'Failed' },
];

export const VISIBILITY_FILTER_OPTIONS: { value: Visibility | ''; label: string }[] = [
  { value: '', label: 'Any visibility' },
  { value: 'all', label: 'All employees' },
  { value: 'department', label: 'Specific departments' },
  { value: 'admin_only', label: 'Admins only' },
];

export const OKF_STATUS_FILTER_OPTIONS: { value: OkfStatus | ''; label: string }[] = [
  { value: '', label: 'All statuses' },
  { value: 'pending_review', label: 'Pending review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'archived', label: 'Archived' },
];

export const SUGGESTIONS: readonly string[] = [
  'Summarize the leave policy',
  'Who is the HR manager?',
  'Explain the leave policy and tell me the carry-forward limit',
  'How long is the notice period?',
];

export const ROUTES = {
  login: '/login',
  signup: '/signup',
  chat: '/app/chat',
  library: '/app/documents',
  dashboard: '/admin/dashboard',
  documents: '/admin/documents',
  document: (id: number | string) => `/admin/documents/${id}`,
  knowledge: '/admin/knowledge',
  knowledgeReview: '/admin/knowledge/review',
  knowledgeDetail: (id: number | string) => `/admin/knowledge/${id}`,
  users: '/admin/users',
  auditLogs: '/admin/audit-logs',
  devUi: '/dev/ui',
} as const;

/** Closed predicate list enforced by the backend (spec §6.2). */
export const RELATION_PREDICATES = [
  'belongs_to',
  'manages',
  'reports_to',
  'governed_by',
  'applies_to',
  'owns',
  'part_of',
  'related_to',
  'supersedes',
] as const;

/**
 * Type-specific `payload` fields (spec §6.2). The plan's `GET /knowledge/schema`
 * endpoint was never implemented, so the manual "New object" form is driven by
 * this local table instead — same field set, same required markers.
 */
export const OKF_FIELD_SPECS: Record<OkfType, OkfFieldSpec[]> = {
  policy: [
    { key: 'title', label: 'Title', type: 'string', required: true },
    { key: 'summary', label: 'Summary', type: 'text', required: true, placeholder: 'Max 500 characters' },
    { key: 'effective_date', label: 'Effective date', type: 'string', required: false, placeholder: 'YYYY-MM-DD' },
    { key: 'owner_department', label: 'Owner department', type: 'string', required: false },
    { key: 'version_label', label: 'Version label', type: 'string', required: false },
    { key: 'rules', label: 'Rules (business-rule keys)', type: 'array', required: false },
  ],
  employee: [
    { key: 'full_name', label: 'Full name', type: 'string', required: true },
    { key: 'job_title', label: 'Job title', type: 'string', required: true },
    { key: 'department', label: 'Department', type: 'string', required: false },
    { key: 'email', label: 'Email', type: 'string', required: false },
    { key: 'phone', label: 'Phone', type: 'string', required: false },
    { key: 'reports_to', label: 'Reports to', type: 'string', required: false },
    { key: 'location', label: 'Location', type: 'string', required: false },
  ],
  department: [
    { key: 'name', label: 'Name', type: 'string', required: true },
    { key: 'head', label: 'Head (employee key)', type: 'string', required: false },
    { key: 'description', label: 'Description', type: 'text', required: false },
    { key: 'email', label: 'Email', type: 'string', required: false },
    { key: 'location', label: 'Location', type: 'string', required: false },
  ],
  product: [
    { key: 'name', label: 'Name', type: 'string', required: true },
    { key: 'description', label: 'Description', type: 'text', required: false },
    { key: 'category', label: 'Category', type: 'string', required: false },
    { key: 'owner_department', label: 'Owner department', type: 'string', required: false },
  ],
  faq: [
    { key: 'question', label: 'Question', type: 'string', required: true },
    { key: 'answer', label: 'Answer', type: 'text', required: true },
    { key: 'category', label: 'Category', type: 'string', required: false },
  ],
  business_rule: [
    { key: 'statement', label: 'Statement', type: 'text', required: true },
    { key: 'subject', label: 'Subject', type: 'string', required: true, placeholder: 'What it governs' },
    { key: 'value', label: 'Value', type: 'string', required: false },
    { key: 'unit', label: 'Unit', type: 'string', required: false },
    { key: 'condition', label: 'Condition', type: 'string', required: false },
    { key: 'applies_to', label: 'Applies to', type: 'array', required: false },
    { key: 'policy', label: 'Policy (policy key)', type: 'string', required: false },
  ],
  asset: [
    { key: 'name', label: 'Name', type: 'string', required: true },
    { key: 'asset_type', label: 'Asset type', type: 'string', required: false },
    { key: 'identifier', label: 'Identifier', type: 'string', required: false },
    { key: 'owner', label: 'Owner', type: 'string', required: false },
    { key: 'location', label: 'Location', type: 'string', required: false },
    { key: 'status', label: 'Status', type: 'string', required: false },
  ],
};

/** Preferred attribute shown as the one-line summary in knowledge tables. */
export const OKF_PRIMARY_ATTRIBUTE: Record<OkfType, string> = {
  policy: 'title',
  employee: 'job_title',
  department: 'description',
  product: 'description',
  faq: 'question',
  business_rule: 'statement',
  asset: 'asset_type',
};

/** Landing route for a signed-in user (spec §13.3). */
export const homeForRole = (role: 'admin' | 'employee' | undefined): string =>
  role === 'admin' ? ROUTES.dashboard : ROUTES.chat;

/** Central TanStack Query key factory — mutations invalidate by prefix. */
export const queryKeys = {
  me: ['me'] as const,
  departments: ['departments'] as const,
  users: (page: number, q: string) => ['users', page, q] as const,
  documents: (filters: Record<string, unknown>) => ['documents', filters] as const,
  document: (id: string) => ['document', id] as const,
  documentStatus: (id: string) => ['document', id, 'status'] as const,
  documentVersions: (id: string) => ['document', id, 'versions'] as const,
  documentText: (id: string) => ['document', id, 'text'] as const,
  documentChunks: (id: string, page: number) => ['document', id, 'chunks', page] as const,
  knowledge: (filters: Record<string, unknown>) => ['knowledge', filters] as const,
  knowledgeItem: (id: string) => ['knowledge', 'item', id] as const,
  knowledgeSchema: ['knowledge', 'schema'] as const,
  conversations: ['conversations'] as const,
  conversation: (id: string) => ['conversation', id] as const,
  adminStats: ['admin', 'stats'] as const,
  auditLogs: (filters: Record<string, unknown>) => ['audit-logs', filters] as const,
} as const;
