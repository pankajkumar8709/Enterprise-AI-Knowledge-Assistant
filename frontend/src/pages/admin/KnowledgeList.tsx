import { BookOpen, Plus, Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { OkfForm } from '@/components/knowledge/OkfForm';
import { TypeBadge } from '@/components/knowledge/TypeBadge';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { TD, TH, THead, TR, TableWrap, TBody } from '@/components/ui/Table';
import { useDebounce } from '@/hooks/useDebounce';
import { KNOWLEDGE_FETCH_LIMIT, useKnowledgeQuery } from '@/hooks/useKnowledge';
import { OKF_STATUS_FILTER_OPTIONS, OKF_TYPE_LABEL, OKF_TYPE_ORDER, ROUTES } from '@/lib/constants';
import { attributeLabel, attributeValue, formatDateTime, formatNumber, formatPercent, pluralize } from '@/lib/format';
import type { OkfStatus, OkfType } from '@/types/api';

const PAGE_SIZE = 20;

export function KnowledgeListPage() {
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get('q') ?? '');
  const debouncedSearch = useDebounce(search, 300);
  const type = (params.get('type') ?? '') as OkfType | '';
  const status = (params.get('status') ?? '') as OkfStatus | '';
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1);
  const [formOpen, setFormOpen] = useState(false);

  useEffect(() => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (debouncedSearch) next.set('q', debouncedSearch);
        else next.delete('q');
        next.delete('page');
        return next;
      },
      { replace: true },
    );
  }, [debouncedSearch, setParams]);

  const knowledge = useKnowledgeQuery(type ? { object_type: type } : undefined);

  const filtered = useMemo(() => {
    const items = knowledge.data?.items ?? [];
    const needle = debouncedSearch.trim().toLowerCase();
    return items.filter((object) => {
      if (status && object.status !== status) return false;
      if (!needle) return true;
      return (
        object.name.toLowerCase().includes(needle) ||
        object.object_key.toLowerCase().includes(needle) ||
        (object.summary ?? '').toLowerCase().includes(needle) ||
        attributeValue(object.payload).toLowerCase().includes(needle)
      );
    });
  }, [debouncedSearch, knowledge.data, status]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visible = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const truncated = (knowledge.data?.total ?? 0) > KNOWLEDGE_FETCH_LIMIT;

  function setParam(key: string, value: string): void {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set(key, value);
        else next.delete(key);
        next.delete('page');
        return next;
      },
      { replace: true },
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Knowledge"
        description="Approved facts and entities extracted from your documents, plus anything authored by hand."
        actions={
          <Button icon={<Plus aria-hidden="true" className="h-4 w-4" />} onClick={() => setFormOpen(true)}>
            New object
          </Button>
        }
      />

      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by type">
          <Button variant={type === '' ? 'secondary' : 'ghost'} size="sm" onClick={() => setParam('type', '')}>
            All types
          </Button>
          {OKF_TYPE_ORDER.map((item) => (
            <Button
              key={item}
              variant={type === item ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setParam('type', item)}
            >
              {OKF_TYPE_LABEL[item]}
            </Button>
          ))}
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label htmlFor="kn-search" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
              Search
            </label>
            <Input
              id="kn-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search names, keys and attributes"
              icon={<Search aria-hidden="true" className="h-4 w-4" />}
            />
          </div>
          <div className="sm:w-48">
            <label htmlFor="kn-status" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
              Status
            </label>
            <Select id="kn-status" value={status} onChange={(event) => setParam('status', event.target.value)}>
              {OKF_STATUS_FILTER_OPTIONS.map((option) => (
                <option key={option.label} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        </div>
      </div>

      {knowledge.isPending ? (
        <div className="rounded-2xl border border-slate-200 bg-white">
          <SkeletonTable rows={6} cols={5} />
        </div>
      ) : knowledge.error ? (
        <div className="rounded-2xl border border-slate-200 bg-white">
          <ErrorState message="Could not load knowledge objects." onRetry={() => void knowledge.refetch()} />
        </div>
      ) : !visible.length ? (
        <div className="rounded-2xl border border-slate-200 bg-white">
          <EmptyState
            icon={<BookOpen aria-hidden="true" className="h-5 w-5" />}
            title="No knowledge objects match"
            hint="Upload documents to extract facts, or create one by hand."
            action={
              <Button icon={<Plus aria-hidden="true" className="h-4 w-4" />} onClick={() => setFormOpen(true)}>
                New object
              </Button>
            }
          />
        </div>
      ) : (
        <TableWrap className="rounded-2xl border border-slate-200 bg-white">
          <THead>
            <TH>Type</TH>
            <TH>Name</TH>
            <TH>Key attribute</TH>
            <TH>Status</TH>
            <TH className="text-right">Confidence</TH>
            <TH className="text-right">Ver.</TH>
            <TH>Updated</TH>
          </THead>
          <TBody>
            {visible.map((object) => {
              const [key, value] = Object.entries(object.payload ?? {})[0] ?? [];
              return (
                <TR key={object.id}>
                  <TD>
                    <TypeBadge type={object.object_type} size="sm" />
                  </TD>
                  <TD>
                    <div className="w-[180px] max-w-[180px] lg:w-[240px] lg:max-w-[240px]">
                      <Link
                        to={ROUTES.knowledgeDetail(object.id)}
                        title={object.name}
                        className="focus-ring block truncate rounded font-medium text-slate-800 hover:text-indigo-700"
                      >
                        {object.name}
                      </Link>
                      <span className="block truncate font-mono text-[11px] text-slate-400" title={object.object_key}>
                        {object.object_key}
                      </span>
                    </div>
                  </TD>
                  <TD className="max-w-[180px]">
                    {key ? (
                      <>
                        <span className="block text-[11px] uppercase tracking-wide text-slate-400">
                          {attributeLabel(key)}
                        </span>
                        <span className="block truncate text-sm text-slate-600" title={attributeValue(value)}>
                          {attributeValue(value)}
                        </span>
                      </>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </TD>
                  <TD>
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
                  </TD>
                  <TD className="text-right tabular-nums text-slate-600">
                    {object.confidence === null ? '—' : formatPercent(object.confidence)}
                  </TD>
                  <TD className="text-right tabular-nums text-slate-500">{object.object_version}</TD>
                  <TD className="whitespace-nowrap text-slate-500">{formatDateTime(object.updated_at)}</TD>
                </TR>
              );
            })}
          </TBody>
        </TableWrap>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-500">
          {formatNumber(filtered.length)} {pluralize(filtered.length, 'object')}
          {status || type || debouncedSearch ? ' matching the current filters' : ''}
          {truncated ? ` · filters apply to the ${KNOWLEDGE_FETCH_LIMIT} most recent` : ''}
        </p>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" disabled={currentPage <= 1} onClick={() => setParam('page', String(currentPage - 1))}>
            Previous
          </Button>
          <span className="text-xs tabular-nums text-slate-500">
            Page {currentPage} / {pageCount}
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={currentPage >= pageCount}
            onClick={() => setParam('page', String(currentPage + 1))}
          >
            Next
          </Button>
        </div>
      </div>

      <OkfForm open={formOpen} onClose={() => setFormOpen(false)} defaultType={type || 'policy'} />
    </div>
  );
}
