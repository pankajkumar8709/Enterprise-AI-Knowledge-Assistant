import { FileText } from 'lucide-react';
import { Link } from 'react-router-dom';

import { cn } from '@/lib/cn';
import { ROUTES } from '@/lib/constants';

export interface SourceQuoteProps {
  quote: string | null;
  documentId?: number | null;
  documentTitle?: string | null;
  page?: number | null;
  className?: string;
}

/**
 * The verbatim snippet a reviewer must see before approving (spec §12.1.5):
 * italic quote with a left indigo border and an "Open document page" link.
 */
export function SourceQuote({ quote, documentId, documentTitle, page, className }: SourceQuoteProps) {
  if (!quote) {
    return (
      <p className={cn('rounded-xl border border-dashed border-slate-200 px-3 py-2 text-xs text-slate-500', className)}>
        No source quote recorded for this object.
      </p>
    );
  }

  return (
    <figure className={cn('border-l-2 border-indigo-300 pl-3', className)}>
      <blockquote className="text-sm italic leading-6 text-slate-600">
        <span aria-hidden="true">“</span>
        {quote}
        <span aria-hidden="true">”</span>
      </blockquote>
      <figcaption className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <FileText aria-hidden="true" className="h-3.5 w-3.5" />
        {documentId ? (
          <Link
            to={ROUTES.document(documentId)}
            className="focus-ring rounded font-medium text-indigo-700 hover:underline"
          >
            Open {documentTitle ?? 'document'}
            {page ? ` — page ${page}` : ''}
          </Link>
        ) : (
          <span>{documentTitle ?? 'Source document removed'}</span>
        )}
      </figcaption>
    </figure>
  );
}

export interface PassageQuoteProps {
  text: string;
  className?: string;
}

/** Highlighted passage style used inside the source drawer. */
export function PassageQuote({ text, className }: PassageQuoteProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-amber-200 bg-amber-50/60 p-4 font-serif text-[15px] leading-7 text-slate-800',
        className,
      )}
    >
      {text}
    </div>
  );
}
