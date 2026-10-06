import { Database, FileText, TriangleAlert } from 'lucide-react';

import { Badge } from '@/components/ui/Badge';
import { cn } from '@/lib/cn';
import { formatPercent } from '@/lib/format';
import { OKF_TYPE_LABEL } from '@/lib/constants';
import type { Source } from '@/types/api';

export interface SourceCardProps {
  source: Source;
  onOpen: (source: Source) => void;
  className?: string;
}

function metaLine(source: Source): string {
  if (source.kind === 'chunk') {
    const parts: string[] = [];
    if (source.section_title) parts.push(source.section_title);
    if (source.page) parts.push(`p.${source.page}`);
    return parts.length ? parts.join(' · ') : 'Document chunk';
  }
  const type = source.okf_type ? (OKF_TYPE_LABEL[source.okf_type] ?? source.okf_type) : 'Fact';
  return `OKF · ${type}`;
}

export function SourceCard({ source, onOpen, className }: SourceCardProps) {
  const missing = source.kind === 'chunk' && source.document_id === null;
  const Icon = source.kind === 'chunk' ? FileText : Database;
  const snippet = source.snippet?.trim();

  return (
    <button
      type="button"
      onClick={() => onOpen(source)}
      className={cn(
        'focus-ring w-full rounded-2xl border border-slate-200 bg-white p-3 text-left transition hover:border-slate-300 hover:shadow-md',
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <Badge color={source.cited ? 'indigo' : 'slate'} size="sm" className="mt-0.5 shrink-0 font-mono">
          {source.ref}
        </Badge>
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
          <Icon aria-hidden="true" className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-900">{source.title || 'Untitled source'}</p>
          <p className="mt-0.5 text-xs text-slate-500">{metaLine(source)}</p>
          {missing ? (
            <p className="mt-1 flex items-center gap-1 text-xs font-medium text-amber-700">
              <TriangleAlert aria-hidden="true" className="h-3 w-3" />
              Source no longer available
            </p>
          ) : snippet ? (
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{snippet}</p>
          ) : null}
          <div className="mt-2 flex items-center gap-2">
            <span className="h-1 w-full max-w-[120px] overflow-hidden rounded-full bg-slate-100">
              <span
                className="block h-full rounded-full bg-indigo-500"
                style={{ width: `${Math.min(Math.max(source.score, 0), 1) * 100}%` }}
              />
            </span>
            <span className="text-[11px] tabular-nums text-slate-400">{formatPercent(source.score)}</span>
          </div>
        </div>
      </div>
    </button>
  );
}
