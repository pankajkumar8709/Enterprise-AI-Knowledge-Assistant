import { useEffect, useRef, type ReactNode } from 'react';

import type { ChatMessage, Source } from '@/types/api';

import { AssistantMessage } from './AssistantMessage';
import { UserMessage } from './UserMessage';

export interface MessageListProps {
  messages: ChatMessage[];
  onOpenSource: (source: Source) => void;
  onRetry: (message: ChatMessage) => void;
  /** Rendered instead of the thread when there are no messages. */
  emptyState?: ReactNode;
  /** Rendered above the thread (e.g. a history error notice). */
  header?: ReactNode;
}

export function MessageList({ messages, onOpenSource, onRetry, emptyState, header }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastId = messages[messages.length - 1]?.id;

  // Keep the newest turn in view as the conversation grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [lastId]);

  if (!messages.length && emptyState) {
    return <div className="py-6">{emptyState}</div>;
  }

  return (
    <div role="log" aria-live="polite" aria-relevant="additions" className="space-y-4">
      {header}
      {messages.map((message) =>
        message.role === 'user' ? (
          <UserMessage key={message.id} message={message} />
        ) : (
          <AssistantMessage key={message.id} message={message} onOpenSource={onOpenSource} onRetry={onRetry} />
        ),
      )}
      <div ref={bottomRef} />
    </div>
  );
}
