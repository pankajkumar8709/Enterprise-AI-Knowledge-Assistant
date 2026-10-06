import { AlertTriangle, Check, ChevronDown, Copy, Info, RotateCw } from 'lucide-react';
import { useMemo, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/cn';
import { formatDateTime, formatLatency } from '@/lib/format';
import { toast } from '@/store/uiStore';
import type { ChatMessage, Source } from '@/types/api';

import { AnswerRenderer } from './AnswerRenderer';
import { ConfidenceBadge } from './ConfidenceBadge';
import { RouteBadge } from './RouteBadge';
import { SourceCard } from './SourceCard';

export interface AssistantMessageProps {
  message: ChatMessage;
  onOpenSource: (source: Source) => void;
  onRetry: (message: ChatMessage) => void;
}

export function AssistantMessage({ message, onOpenSource, onRetry }: AssistantMessageProps) {
  const [showSources, setShowSources] = useState(false);
  const [copied, setCopied] = useState(false);
  const answer = message.answer;

  const { cited, related } = useMemo(() => {
    const sources = answer?.sources ?? [];
    return {
      cited: sources.filter((source) => source.cited),
      related: sources.filter((source) => !source.cited),
    };
  }, [answer]);

  // 1. Waiting on the model.
  if (message.pending) {
    return (
      <Card className="p-5" aria-busy="true">
        <div className="space-y-2" role="status">
          <Skeleton className="h-3.5 w-full" />
          <Skeleton className="h-3.5 w-11/12" />
          <Skeleton className="h-3.5 w-2/3" />
        </div>
        <p className="mt-3 flex items-center gap-2 text-xs text-slate-500">
          <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-500" />
          Searching company knowledge…
        </p>
      </Card>
    );
  }

  // 2. Network / 5xx failure with a retry action.
  if (message.error) {
    return (
      <Card tone="danger" className="p-5">
        <div className="flex items-start gap-3">
          <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-rose-900">The answer could not be generated</p>
            <p className="mt-0.5 text-sm text-rose-800">{message.content}</p>
          </div>
        </div>
        <div className="mt-3 flex justify-end">
          <Button
            variant="secondary"
            size="sm"
            icon={<RotateCw aria-hidden="true" className="h-3.5 w-3.5" />}
            onClick={() => onRetry(message)}
          >
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  // 3. Nothing relevant was found — neutral card, no badges (kept in history).
  if (answer && !answer.answerable) {
    return (
      <Card className="p-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
            <Info aria-hidden="true" className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <AnswerRenderer text={message.content} sources={[]} onOpen={onOpenSource} />
            <p className="mt-2 text-xs text-slate-500">
              Try rephrasing, naming the document or team, or asking for a narrower detail.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  // 4. A grounded answer.
  return (
    <Card className="p-5">
      {answer ? (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <RouteBadge route={answer.route} />
          <ConfidenceBadge label={answer.confidence_label} value={answer.confidence} />
          <span className="ml-auto text-[11px] tabular-nums text-slate-400">
            {formatLatency(answer.latency_ms)}
          </span>
        </div>
      ) : null}

      <AnswerRenderer text={message.content} sources={answer?.sources ?? []} onOpen={onOpenSource} />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            icon={
              copied ? (
                <Check aria-hidden="true" className="h-3.5 w-3.5 text-emerald-600" />
              ) : (
                <Copy aria-hidden="true" className="h-3.5 w-3.5" />
              )
            }
            onClick={() => {
              void navigator.clipboard.writeText(message.content).then(() => {
                setCopied(true);
                toast.success('Answer copied');
                window.setTimeout(() => setCopied(false), 2000);
              });
            }}
          >
            {copied ? 'Copied' : 'Copy'}
          </Button>
          <span className="text-[11px] text-slate-400">{formatDateTime(message.created_at)}</span>
        </div>

        {answer?.sources.length ? (
          <Button
            variant="ghost"
            size="sm"
            aria-expanded={showSources}
            aria-controls={`sources-${message.id}`}
            onClick={() => setShowSources((open) => !open)}
            iconRight={
              <ChevronDown
                aria-hidden="true"
                className={cn('h-3.5 w-3.5 transition-transform', showSources && 'rotate-180')}
              />
            }
          >
            Sources ({answer.sources.length})
          </Button>
        ) : null}
      </div>

      {showSources && answer?.sources.length ? (
        <div id={`sources-${message.id}`} className="mt-3 space-y-3">
          {cited.length ? (
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Cited in the answer</p>
              {cited.map((source) => (
                <SourceCard key={`${source.ref}-${source.kind}`} source={source} onOpen={onOpenSource} />
              ))}
            </div>
          ) : null}
          {related.length ? (
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Related sources</p>
              {related.map((source) => (
                <SourceCard key={`${source.ref}-${source.kind}`} source={source} onOpen={onOpenSource} />
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
