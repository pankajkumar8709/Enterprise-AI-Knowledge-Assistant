import { cn } from '@/lib/cn';
import { attributeLabel, attributeValue } from '@/lib/format';

export interface AttributeTableProps {
  attributes: Record<string, unknown>;
  /** Restrict and order the displayed keys. */
  keys?: string[];
  className?: string;
  dense?: boolean;
}

/** Two-column key/value table; keys are small uppercase captions. */
export function AttributeTable({ attributes, keys, className, dense = false }: AttributeTableProps) {
  const entries = (keys ?? Object.keys(attributes))
    .filter((key) => attributes[key] !== undefined && attributes[key] !== null && attributes[key] !== '')
    .map((key) => [key, attributes[key]] as const);

  if (!entries.length) {
    return <p className="text-sm text-slate-500">No attributes recorded.</p>;
  }

  return (
    <dl className={cn('divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200', className)}>
      {entries.map(([key, value]) => (
        <div key={key} className="grid grid-cols-1 gap-1 px-3 py-2 sm:grid-cols-[180px_1fr] sm:gap-4">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{attributeLabel(key)}</dt>
          <dd className={cn('text-slate-700', dense ? 'text-xs leading-5' : 'text-sm leading-6')}>
            {attributeValue(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}
