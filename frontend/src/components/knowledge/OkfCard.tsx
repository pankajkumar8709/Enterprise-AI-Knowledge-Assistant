import { Check, Pencil, ShieldCheck, X } from 'lucide-react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { cn } from '@/lib/cn';
import { formatPercent } from '@/lib/format';
import type { OkfObjectDto } from '@/types/api';

import { AttributeTable } from './AttributeTable';
import { SourceQuote } from './SourceQuote';
import { TypeBadge } from './TypeBadge';

export interface OkfCardProps {
  object: OkfObjectDto;
  /** Shows the review checkbox (review queue only). */
  selectable?: boolean;
  selected?: boolean;
  onToggleSelect?: (id: number, selected: boolean) => void;
  onApprove?: (object: OkfObjectDto) => void;
  onReject?: (object: OkfObjectDto) => void;
  onEdit?: (object: OkfObjectDto) => void;
  onOpen?: (object: OkfObjectDto) => void;
  busy?: boolean;
  className?: string;
}

const CONFIDENCE_TONE = (value: number) =>
  value >= 0.75 ? 'bg-emerald-500' : value >= 0.5 ? 'bg-amber-500' : 'bg-rose-500';

export function OkfCard({
  object,
  selectable = false,
  selected = false,
  onToggleSelect,
  onApprove,
  onReject,
  onEdit,
  onOpen,
  busy = false,
  className,
}: OkfCardProps) {
  const confidence = object.confidence;

  return (
    <Card className={cn('flex flex-col', selected && 'ring-2 ring-indigo-500 ring-offset-1', className)}>
      <CardHeader>
        <div className="flex min-w-0 items-start gap-3">
          {selectable ? (
            <input
              type="checkbox"
              checked={selected}
              aria-label={`Select ${object.name}`}
              onChange={(event) => onToggleSelect?.(object.id, event.target.checked)}
              className="mt-1 h-4 w-4 shrink-0 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            />
          ) : null}
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <TypeBadge type={object.object_type} />
              <Badge color="slate" size="sm" className="font-mono">
                v{object.object_version}
              </Badge>
              {object.status !== 'pending_review' ? (
                <Badge color={object.status === 'approved' ? 'emerald' : 'slate'} size="sm">
                  {object.status}
                </Badge>
              ) : null}
            </div>
            <CardTitle className="mt-2 text-base leading-6">
              {onOpen ? (
                <button type="button" onClick={() => onOpen(object)} className="focus-ring rounded text-left hover:text-indigo-700">
                  {object.name}
                </button>
              ) : (
                object.name
              )}
            </CardTitle>
            <p className="mt-0.5 font-mono text-[11px] text-slate-400">{object.object_key}</p>
          </div>
        </div>

        {confidence !== null ? (
          <div className="w-24 shrink-0 text-right">
            <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Confidence</p>
            <p className="text-sm font-semibold tabular-nums text-slate-800">{formatPercent(confidence)}</p>
            <span className="mt-1 block h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
              <span
                className={cn('block h-full rounded-full', CONFIDENCE_TONE(confidence))}
                style={{ width: `${Math.min(Math.max(confidence, 0), 1) * 100}%` }}
              />
            </span>
          </div>
        ) : null}
      </CardHeader>

      <CardBody className="flex-1 space-y-3 pt-3">
        {object.summary ? <p className="text-sm leading-6 text-slate-600">{object.summary}</p> : null}
        <AttributeTable attributes={object.payload} dense />
        <SourceQuote
          quote={object.source_excerpt}
          documentId={object.source_document_id}
          documentTitle={null}
          page={null}
        />
        {object.relations.length ? (
          <div className="flex flex-wrap gap-1.5">
            {object.relations.map((relation) => (
              <Badge key={`${relation.relation_type}-${relation.target_name}`} color="sky" size="sm">
                {relation.relation_type} → {relation.target_name}
              </Badge>
            ))}
          </div>
        ) : null}
      </CardBody>

      {onApprove || onReject || onEdit ? (
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-100 px-5 py-3">
          {onReject ? (
            <Button
              variant="ghost"
              size="sm"
              disabled={busy}
              icon={<X aria-hidden="true" className="h-3.5 w-3.5" />}
              onClick={() => onReject(object)}
            >
              Reject
            </Button>
          ) : null}
          {onEdit ? (
            <Button
              variant="secondary"
              size="sm"
              disabled={busy}
              icon={<Pencil aria-hidden="true" className="h-3.5 w-3.5" />}
              onClick={() => onEdit(object)}
            >
              Edit
            </Button>
          ) : null}
          {onApprove ? (
            <Button
              size="sm"
              loading={busy}
              icon={<Check aria-hidden="true" className="h-3.5 w-3.5" />}
              onClick={() => onApprove(object)}
            >
              Approve
            </Button>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}

/** Small header used on the knowledge detail page. */
export function OkfHeader({ object }: { object: OkfObjectDto }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <TypeBadge type={object.object_type} />
      <Badge color="slate" size="sm" className="font-mono">
        {object.object_key}
      </Badge>
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
      <Badge color="indigo" size="sm">
        <ShieldCheck aria-hidden="true" className="h-3 w-3" />
        v{object.object_version}
      </Badge>
    </div>
  );
}
