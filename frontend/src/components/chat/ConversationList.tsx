import { MessageSquarePlus, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/cn';
import { relativeTime } from '@/lib/format';
import type { ConversationDto } from '@/types/domain';

export interface ConversationListProps {
  conversations: ConversationDto[];
  activeId: number | null;
  loading: boolean;
  error: unknown;
  onSelect: (id: number) => void;
  onNew: () => void;
  onDelete: (id: number) => void;
  onRetry: () => void;
  deleting?: boolean;
}

export function ConversationList({
  conversations,
  activeId,
  loading,
  error,
  onSelect,
  onNew,
  onDelete,
  onRetry,
  deleting = false,
}: ConversationListProps) {
  const [pendingDelete, setPendingDelete] = useState<ConversationDto | null>(null);

  return (
    <div className="flex h-full flex-col gap-3">
      <Button block icon={<MessageSquarePlus aria-hidden="true" className="h-4 w-4" />} onClick={onNew}>
        New chat
      </Button>

      <div className="thin-scrollbar -mx-1 flex-1 overflow-y-auto px-1">
        {loading ? (
          <div className="space-y-2 p-1">
            {[0, 1, 2, 3].map((index) => (
              <Skeleton key={index} className="h-12 w-full rounded-xl" />
            ))}
          </div>
        ) : error ? (
          <ErrorState compact message="Could not load your conversations." onRetry={onRetry} />
        ) : !conversations.length ? (
          <EmptyState
            icon={<MessageSquarePlus aria-hidden="true" className="h-5 w-5" />}
            title="No conversations yet"
            hint="Ask your first question to start a thread."
          />
        ) : (
          <ul className="space-y-1">
            {conversations.map((conversation) => {
              const active = conversation.id === activeId;
              return (
                <li key={conversation.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => onSelect(conversation.id)}
                    aria-current={active ? 'true' : undefined}
                    className={cn(
                      'focus-ring flex w-full items-start justify-between gap-2 rounded-xl px-3 py-2 pr-9 text-left transition',
                      active ? 'bg-indigo-50 text-indigo-800' : 'text-slate-600 hover:bg-slate-100',
                    )}
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">
                        {conversation.title?.trim() || 'New conversation'}
                      </span>
                      <span className="block text-[11px] text-slate-400">{relativeTime(conversation.created_at)}</span>
                    </span>
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete conversation ${conversation.title ?? ''}`.trim()}
                    onClick={() => setPendingDelete(conversation)}
                    className="focus-ring absolute right-1.5 top-2 rounded-lg p-1.5 text-slate-400 opacity-0 transition hover:bg-white hover:text-rose-600 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <Trash2 aria-hidden="true" className="h-3.5 w-3.5" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete conversation"
        message={`"${pendingDelete?.title ?? 'This conversation'}" and its messages will be permanently removed.`}
        confirmLabel="Delete"
        loading={deleting}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) onDelete(pendingDelete.id);
          setPendingDelete(null);
        }}
      />
    </div>
  );
}
