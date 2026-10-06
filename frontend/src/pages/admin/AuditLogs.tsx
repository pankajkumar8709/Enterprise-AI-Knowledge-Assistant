import { ScrollText, Search } from 'lucide-react';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { TD, TH, THead, TR, TableWrap, TBody } from '@/components/ui/Table';
import { useAuditLogsQuery, useUsersQuery } from '@/hooks/useAdmin';
import { useDebounce } from '@/hooks/useDebounce';
import { formatDateTime, formatNumber } from '@/lib/format';

const PAGE_SIZE = 20;

/** Frequent actions, offered as datalist hints (free text is still allowed). */
const KNOWN_ACTIONS = [
  'document.upload',
  'document.update',
  'document.download',
  'document.delete',
  'document.reprocess',
  'acl.change',
  'okf.approve',
  'okf.reject',
  'okf.create',
  'okf.update',
  'okf.archive',
  'chat.query',
  'user.create',
  'user.update',
  'department.create',
  'department.update',
  'department.delete',
  'admin.audit_logs.read',
];

function toIsoStart(date: string): string | undefined {
  return date ? `${date}T00:00:00Z` : undefined;
}

function toIsoEnd(date: string): string | undefined {
  return date ? `${date}T23:59:59Z` : undefined;
}

export function AuditLogsPage() {
  const [params, setParams] = useSearchParams();
  const users = useUsersQuery();
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1);

  const [action, setAction] = useState(params.get('action') ?? '');
  const debouncedAction = useDebounce(action, 300);
  const userId = params.get('user_id') ?? '';
  const from = params.get('from') ?? '';
  const to = params.get('to') ?? '';

  const logs = useAuditLogsQuery({
    page,
    page_size: PAGE_SIZE,
    ...(userId ? { user_id: Number(userId) } : {}),
    ...(debouncedAction ? { action: debouncedAction } : {}),
    ...(from ? { from: toIsoStart(from) } : {}),
    ...(to ? { to: toIsoEnd(to) } : {}),
  });

  const total = logs.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function setParam(key: string, value: string): void {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set(key, value);
        else next.delete(key);
        if (key !== 'page') next.delete('page');
        return next;
      },
      { replace: true },
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Audit logs"
        description="Every privileged action is recorded: uploads, ACL changes, reviews and chat queries."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardBody className="grid gap-3 pt-2 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label htmlFor="audit-action" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
              Action
            </label>
            <Input
              id="audit-action"
              list="audit-actions"
              value={action}
              onChange={(event) => {
                setAction(event.target.value);
                setParam('action', event.target.value);
              }}
              placeholder="document.upload"
              icon={<Search aria-hidden="true" className="h-4 w-4" />}
            />
            <datalist id="audit-actions">
              {KNOWN_ACTIONS.map((known) => (
                <option key={known} value={known} />
              ))}
            </datalist>
          </div>

          <div>
            <label htmlFor="audit-user" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
              User
            </label>
            <Select id="audit-user" value={userId} onChange={(event) => setParam('user_id', event.target.value)}>
              <option value="">All users</option>
              {(users.data ?? []).map((user) => (
                <option key={user.id} value={user.id}>
                  {user.full_name}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <label htmlFor="audit-from" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
              From
            </label>
            <Input id="audit-from" type="date" value={from} onChange={(event) => setParam('from', event.target.value)} />
          </div>

          <div>
            <label htmlFor="audit-to" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
              To
            </label>
            <Input id="audit-to" type="date" value={to} onChange={(event) => setParam('to', event.target.value)} />
          </div>

          {action || userId || from || to ? (
            <div className="sm:col-span-2 lg:col-span-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setAction('');
                  setParams(new URLSearchParams(), { replace: true });
                }}
              >
                Clear filters
              </Button>
            </div>
          ) : null}
        </CardBody>
      </Card>

      <div className="rounded-2xl border border-slate-200 bg-white">
        {logs.isPending ? (
          <SkeletonTable rows={8} cols={5} />
        ) : logs.error ? (
          <ErrorState message="Could not load the audit trail." onRetry={() => void logs.refetch()} />
        ) : !logs.data?.items.length ? (
          <EmptyState
            icon={<ScrollText aria-hidden="true" className="h-5 w-5" />}
            title="No audit entries match"
            hint="Adjust the filters or widen the date range."
          />
        ) : (
          <TableWrap>
            <THead>
              <TH>When</TH>
              <TH>Action</TH>
              <TH>Entity</TH>
              <TH>Details</TH>
              <TH>Source</TH>
            </THead>
            <TBody>
              {logs.data.items.map((log) => {
                const user = (users.data ?? []).find((candidate) => candidate.id === log.user_id);
                return (
                  <TR key={log.id}>
                    <TD className="whitespace-nowrap text-xs text-slate-500">{formatDateTime(log.created_at)}</TD>
                    <TD>
                      <Badge color="indigo" size="sm" className="font-mono">
                        {log.action}
                      </Badge>
                    </TD>
                    <TD>
                      {log.entity_type ? (
                        <>
                          <span className="block text-sm text-slate-700">{log.entity_type}</span>
                          {log.entity_id ? (
                            <span className="block font-mono text-[11px] text-slate-400">{log.entity_id}</span>
                          ) : null}
                        </>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </TD>
                    <TD className="max-w-[200px]">
                      {log.metadata ? (
                        <code className="block truncate font-mono text-[11px] text-slate-600" title={JSON.stringify(log.metadata)}>
                          {JSON.stringify(log.metadata)}
                        </code>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </TD>
                    <TD>
                      <div className="flex max-w-[180px] items-center gap-2">
                        {user ? (
                          <>
                            <Avatar name={user.full_name} size="sm" />
                            <span className="truncate text-xs text-slate-600" title={user.full_name}>
                              {user.full_name}
                            </span>
                          </>
                        ) : (
                          <span className="text-xs text-slate-400">system</span>
                        )}
                        {log.ip ? (
                          <span className="font-mono text-[11px] text-slate-400" title={log.ip}>
                            {log.ip}
                          </span>
                        ) : null}
                      </div>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </TableWrap>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-500">{formatNumber(total)} entries</p>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setParam('page', String(page - 1))}>
            Previous
          </Button>
          <span className="text-xs tabular-nums text-slate-500">
            Page {page} / {pageCount}
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= pageCount}
            onClick={() => setParam('page', String(page + 1))}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
