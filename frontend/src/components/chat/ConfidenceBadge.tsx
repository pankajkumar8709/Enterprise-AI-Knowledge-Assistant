import { Tooltip } from '@/components/ui/Tooltip';
import { Badge, type BadgeProps } from '@/components/ui/Badge';
import { CONFIDENCE_LABEL } from '@/lib/constants';
import { formatPercent } from '@/lib/format';
import type { ConfidenceLabel } from '@/types/api';

const CONFIDENCE_COLOR: Record<ConfidenceLabel, NonNullable<BadgeProps['color']>> = {
  high: 'emerald',
  medium: 'amber',
  low: 'rose',
};

export function ConfidenceBadge({
  label,
  value,
  className,
}: {
  label: ConfidenceLabel;
  value?: number;
  className?: string;
}) {
  const title = `${CONFIDENCE_LABEL[label] ?? 'Confidence'}${value === undefined ? '' : ` — ${formatPercent(value)}`}`;
  return (
    <Tooltip content={title}>
      <Badge color={CONFIDENCE_COLOR[label] ?? 'slate'} className={className}>
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
        {value === undefined ? (CONFIDENCE_LABEL[label] ?? label) : formatPercent(value)}
      </Badge>
    </Tooltip>
  );
}
