import { History, Sparkles } from 'lucide-react';
import { useState } from 'react';

import { Drawer } from '@/components/ui/Drawer';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { useAuth } from '@/hooks/useAuth';
import { useChatSession, useConversationsQuery, useDeleteConversation } from '@/hooks/useChat';
import type { Source } from '@/types/api';

import { ChatInput } from './ChatInput';
import { ConversationList } from './ConversationList';
import { MessageList } from './MessageList';
import { SourcePanel } from './SourcePanel';
import { SuggestionCards } from './SuggestionCards';

export interface ChatWindowProps {
  conversationId: number | null;
  onSelectConversation: (id: number | null) => void;
}

export function ChatWindow({ conversationId, onSelectConversation }: ChatWindowProps) {
  const { user } = useAuth();
  const session = useChatSession(conversationId);
  const conversations = useConversationsQuery();
  const deleteConversation = useDeleteConversation();
  const [openSource, setOpenSource] = useState<Source | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  const firstName = user?.full_name?.split(' ')[0] ?? 'there';

  const list = (
    <ConversationList
      conversations={conversations.data ?? []}
      activeId={session.activeId}
      loading={conversations.isPending}
      error={conversations.error}
      deleting={deleteConversation.isPending}
      onSelect={(id) => {
        onSelectConversation(id);
        setHistoryOpen(false);
      }}
      onNew={() => {
        onSelectConversation(null);
        setHistoryOpen(false);
      }}
      onDelete={(id) => {
        deleteConversation.mutate(id, {
          onSuccess: () => {
            if (id === session.activeId) onSelectConversation(null);
          },
        });
      }}
      onRetry={() => void conversations.refetch()}
    />
  );

  return (
    <div className="flex min-h-[calc(100vh-8rem)] gap-6">
      <aside className="hidden w-72 shrink-0 lg:block">
        <div className="sticky top-20 h-[calc(100vh-8rem)] rounded-2xl border border-slate-200 bg-white p-3">
          {list}
        </div>
      </aside>

      <Drawer open={historyOpen} onClose={() => setHistoryOpen(false)} title="Conversations" side="left" widthClassName="w-72">
        <div className="-mx-5 -my-4 h-[calc(100vh-9rem)] p-3">{list}</div>
      </Drawer>

      <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold tracking-tight text-slate-900">
              {session.activeId ? 'Conversation' : `Hi ${firstName}`}
            </h1>
            <p className="mt-0.5 text-sm text-slate-500">
              {session.activeId
                ? 'Follow-ups use the earlier turns of this conversation.'
                : 'Answers come from approved company facts and the documents you can access.'}
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            className="lg:hidden"
            icon={<History aria-hidden="true" className="h-3.5 w-3.5" />}
            onClick={() => setHistoryOpen(true)}
          >
            History
          </Button>
        </div>

        {session.historyError ? (
          <ErrorState message="This conversation could not be loaded." onRetry={() => window.location.reload()} compact />
        ) : session.isLoadingHistory ? (
          <div className="space-y-3">
            <Skeleton className="h-16 w-2/3 rounded-2xl" />
            <Skeleton className="h-28 w-full rounded-2xl" />
          </div>
        ) : (
          <MessageList
            messages={session.messages}
            onOpenSource={setOpenSource}
            onRetry={(message) => void session.retry(message)}
            emptyState={
              <div className="space-y-6">
                <div className="flex items-start gap-3 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-4">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-indigo-600 shadow-sm">
                    <Sparkles aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <p className="text-sm leading-6 text-slate-700">
                    Ask a question in plain language. Every answer lists the sources it used, and you can open each one
                    to read the passage it came from.
                  </p>
                </div>
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Try asking</p>
                  <SuggestionCards onSelect={(question) => void session.send(question)} />
                </div>
              </div>
            }
          />
        )}

        <div className="sticky bottom-4 mt-auto">
          <ChatInput onSend={(content) => void session.send(content)} disabled={session.isSending} />
        </div>
      </section>

      <SourcePanel source={openSource} onClose={() => setOpenSource(null)} />
    </div>
  );
}
