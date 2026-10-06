import { Check, TriangleAlert, Upload } from 'lucide-react';

import { Badge, type BadgeProps } from '@/components/ui/Badge';
import { DOC_STATUS_LABEL } from '@/lib/constants';
import type { DocStatus } from '@/types/api';

const STATUS_COLOR: Record<DocStatus, NonNullable<BadgeProps['color']>> = {
  uploaded: 'slate',
  processing: 'sky',
  ready: 'emerald',
  failed: 'rose',
};

/** Uploaded=slate, Processing=sky (animated dot), Ready=emerald, Failed=rose. */
export function StatusBadge({ status, className }: { status: DocStatus; className?: string }) {
  const dot =
    status === 'processing' ? (
      <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-500" />
    ) : status === 'ready' ? (
      <Check aria-hidden="true" className="h-3 w-3" />
    ) : status === 'failed' ? (
      <TriangleAlert aria-hidden="true" className="h-3 w-3" />
    ) : (
      <Upload aria-hidden="true" className="h-3 w-3" />
    );

  return (
    <Badge color={STATUS_COLOR[status] ?? 'slate'} dot={dot} className={className}>
      {DOC_STATUS_LABEL[status] ?? status}
    </Badge>
  );
}
