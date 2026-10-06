import { History } from 'lucide-react';

import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatBytes, formatDateTime } from '@/lib/format';
import type { DocumentVersionDto } from '@/types/domain';

export interface VersionListProps {
  versions: DocumentVersionDto[] | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  currentVersion?: number;
}

export function VersionList({ versions, loading, error, onRetry, currentVersion }: VersionListProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[0, 1].map((index) => (
          <Skeleton key={index} className="h-12 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (error) {
    return <ErrorState compact message="Could not load the version history." onRetry={onRetry} />;
  }

  if (!versions?.length) {
    return <EmptyState icon={<History aria-hidden="true" className="h-5 w-5" />} title="No versions recorded" />;
  }

  return (
    <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200">
      {versions.map((version) => (
        <li key={version.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-sm font-medium text-slate-800">
              Version {version.version}
              {version.version === currentVersion ? (
                <Badge color="indigo" size="sm">
                  current
                </Badge>
              ) : null}
            </p>
            <p className="text-xs text-slate-500">
              {formatDateTime(version.created_at)}
              {version.note ? ` — ${version.note}` : ''}
            </p>
          </div>
          <span className="text-xs tabular-nums text-slate-500">{formatBytes(version.size_bytes)}</span>
        </li>
      ))}
    </ul>
  );
}
