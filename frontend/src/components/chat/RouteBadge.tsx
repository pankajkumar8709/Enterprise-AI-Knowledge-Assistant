import { Database, FileText, Layers } from 'lucide-react';

import { Badge, type BadgeProps } from '@/components/ui/Badge';
import { ROUTE_LABEL } from '@/lib/constants';
import type { ChatRoute } from '@/types/api';

const ROUTE_STYLE: Record<ChatRoute, { color: NonNullable<BadgeProps['color']>; icon: typeof Database }> = {
  structured: { color: 'violet', icon: Database },
  document: { color: 'sky', icon: FileText },
  mixed: { color: 'indigo', icon: Layers },
};

/** Structured → "Facts" (violet), Document → "Documents" (sky), Mixed → "Facts + Documents" (indigo). */
export function RouteBadge({ route }: { route: ChatRoute }) {
  const style = ROUTE_STYLE[route] ?? ROUTE_STYLE.mixed;
  const Icon = style.icon;
  return (
    <Badge color={style.color}>
      <Icon aria-hidden="true" className="h-3 w-3" />
      {ROUTE_LABEL[route] ?? route}
    </Badge>
  );
}
