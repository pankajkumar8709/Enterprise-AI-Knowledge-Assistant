import { Badge, type BadgeProps } from '@/components/ui/Badge';
import { OKF_TYPE_LABEL } from '@/lib/constants';
import type { OkfType } from '@/types/api';

const TYPE_COLOR: Record<OkfType, NonNullable<BadgeProps['color']>> = {
  policy: 'indigo',
  employee: 'sky',
  department: 'violet',
  product: 'emerald',
  faq: 'amber',
  business_rule: 'rose',
  asset: 'slate',
};

/** Colour-coded badge for the seven OKF object types (spec §6.2). */
export function TypeBadge({
  type,
  className,
  size = 'md',
}: {
  type: OkfType;
  className?: string;
  size?: BadgeProps['size'];
}) {
  return (
    <Badge color={TYPE_COLOR[type] ?? 'slate'} size={size} className={className}>
      {OKF_TYPE_LABEL[type] ?? type}
    </Badge>
  );
}

export function okfTypeColor(type: OkfType): NonNullable<BadgeProps['color']> {
  return TYPE_COLOR[type] ?? 'slate';
}
