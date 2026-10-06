import { Download, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';

import { AttributeTable } from '@/components/knowledge/AttributeTable';
import { PassageQuote, SourceQuote } from '@/components/knowledge/SourceQuote';
import { TypeBadge } from '@/components/knowledge/TypeBadge';
import { Button, buttonVariants } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { useDownloadDocument } from '@/hooks/useDocuments';
import { useAuth } from '@/hooks/useAuth';
import { ROUTES } from '@/lib/constants';
import { formatPercent } from '@/lib/format';
import type { Source } from '@/types/api';

export interface SourcePanelProps {
  source: Source | null;
  onClose: () => void;
}

/** Right drawer (`w-[420px]`, full width on mobile) with the cited passage or fact. */
export function SourcePanel({ source, onClose }: SourcePanelProps) {
  const { isAdmin } = useAuth();
  const download = useDownloadDocument();
  const open = source !== null;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={source?.title || 'Source'}
      description={
        source
          ? source.kind === 'chunk'
            ? [source.section_title, source.page ? `page ${source.page}` : null].filter(Boolean).join(' · ') ||
              'Document passage'
            : 'Approved knowledge fact'
          : undefined
      }
      footer={
        source ? (
          <>
            {source.kind === 'chunk' && source.document_id !== null && isAdmin ? (
              <Link
                to={ROUTES.document(source.document_id)}
                className={buttonVariants({ variant: 'secondary', size: 'sm' })}
                onClick={onClose}
              >
                <ExternalLink aria-hidden="true" className="h-3.5 w-3.5" />
                Open document
              </Link>
            ) : null}
            {source.kind === 'chunk' && source.document_id !== null ? (
              <Button
                size="sm"
                icon={<Download aria-hidden="true" className="h-3.5 w-3.5" />}
                loading={download.isPending}
                onClick={() => download.mutate({ id: source.document_id as number, source_name: source.title })}
              >
                Download document
              </Button>
            ) : null}
            {source.kind === 'okf' && source.origin?.document_id ? (
              <Link
                to={ROUTES.document(source.origin.document_id)}
                className={buttonVariants({ variant: 'secondary', size: 'sm' })}
                onClick={onClose}
              >
                <ExternalLink aria-hidden="true" className="h-3.5 w-3.5" />
                Open source document
              </Link>
            ) : null}
          </>
        ) : null
      }
    >
      {source ? <SourcePanelBody source={source} /> : null}
    </Drawer>
  );
}

function SourcePanelBody({ source }: { source: Source }) {
  if (source.kind === 'chunk') {
    return (
      <div className="space-y-4">
        {source.document_id === null ? (
          <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            This document was deleted after the answer was generated, so the passage is no longer available.
          </p>
        ) : source.snippet ? (
          <PassageQuote text={source.snippet} />
        ) : (
          <p className="text-sm text-slate-500">No passage text stored for this source.</p>
        )}

        <dl className="space-y-2 text-sm">
          <MetaRow label="Document" value={source.title} />
          <MetaRow label="Section" value={source.section_title ?? '—'} />
          <MetaRow label="Page" value={source.page ? String(source.page) : '—'} />
          <MetaRow label="Relevance" value={formatPercent(source.score)} />
          <MetaRow label="Reference" value={source.ref} mono />
        </dl>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {source.okf_type ? <TypeBadge type={source.okf_type} /> : null}
        <span className="text-xs text-slate-500">Confidence {formatPercent(source.score)}</span>
      </div>

      {Object.keys(source.facts ?? {}).length ? (
        <AttributeTable attributes={source.facts} />
      ) : (
        <p className="text-sm text-slate-500">No attributes recorded for this fact.</p>
      )}

      {source.snippet ? (
        <SourceQuote
          quote={source.snippet}
          documentId={source.origin?.document_id ?? null}
          documentTitle={source.origin?.document_title ?? null}
          page={source.origin?.page ?? null}
        />
      ) : source.origin ? (
        <p className="text-xs text-slate-500">
          Derived from {source.origin.document_title ?? 'a document'}
          {source.origin.page ? `, page ${source.origin.page}` : ''}.
        </p>
      ) : null}
    </div>
  );
}

function MetaRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-2">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className={mono ? 'font-mono text-xs text-slate-700' : 'text-right text-sm text-slate-700'}>{value}</dd>
    </div>
  );
}
