import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo, useRef, useState } from 'react';

import { api, apiErrorMessage } from '@/lib/api';
import { queryKeys } from '@/lib/constants';
import { toast } from '@/store/uiStore';
import type { ChatAnswer, ChatMessage } from '@/types/api';
import type { ConversationDetailDto, ConversationDto, ConversationMessageDto } from '@/types/domain';

export function useConversationsQuery() {
  return useQuery({
    queryKey: queryKeys.conversations,
    queryFn: async () => {
      const { data } = await api.get<ConversationDto[]>('/chat/conversations');
      return data;
    },
    staleTime: 30_000,
  });
}

export function useConversationQuery(id: number | null) {
  return useQuery({
    queryKey: queryKeys.conversation(String(id)),
    queryFn: async () => {
      const { data } = await api.get<ConversationDetailDto>(`/chat/conversations/${id}`);
      return data;
    },
    enabled: id !== null && Number.isFinite(id),
    staleTime: 30_000,
  });
}

export function useCreateConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<ConversationDto>('/chat/conversations', {});
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
    },
    onError: (error) => toast.error('Could not start a new chat', apiErrorMessage(error)),
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/chat/conversations/${id}`);
      return id;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
      toast.success('Conversation deleted');
    },
    onError: (error) => toast.error('Could not delete the conversation', apiErrorMessage(error)),
  });
}

function toChatMessage(message: ConversationMessageDto): ChatMessage {
  return {
    id: `m${message.id}`,
    role: message.role,
    content: message.content,
    created_at: message.created_at,
  };
}

function answerToMessage(answer: ChatAnswer): ChatMessage {
  return {
    id: `a${answer.message_id}`,
    role: 'assistant',
    content: answer.answer,
    created_at: new Date().toISOString(),
    answer,
  };
}

let localSeq = 0;
function localId(prefix: string): string {
  localSeq += 1;
  return `${prefix}-${localSeq}-${Date.now()}`;
}

export interface ChatSession {
  /** Conversation currently displayed (null until the first message creates one). */
  activeId: number | null;
  messages: ChatMessage[];
  isSending: boolean;
  isLoadingHistory: boolean;
  historyError: unknown;
  send: (content: string) => Promise<void>;
  retry: (assistantMessage: ChatMessage) => Promise<void>;
}

/**
 * Owns the optimistic chat session: the user bubble appears instantly, an
 * assistant placeholder shows the "Searching company knowledge…" skeleton, and
 * the answer (or a retryable error card) replaces it when the request settles.
 */
export function useChatSession(urlConversationId: number | null): ChatSession {
  const queryClient = useQueryClient();
  const [createdId, setCreatedId] = useState<number | null>(null);
  const [sessions, setSessions] = useState<Record<number, ChatMessage[]>>({});
  const [isSending, setIsSending] = useState(false);
  const sendingRef = useRef(false);

  const activeId = urlConversationId ?? createdId;
  const key = activeId ?? 0;

  const detail = useConversationQuery(activeId);
  const history = useMemo<ChatMessage[]>(
    () => (detail.data?.messages ?? []).map(toChatMessage),
    [detail.data],
  );
  const sessionMessages = useMemo(() => sessions[key] ?? [], [sessions, key]);
  const messages = useMemo(() => [...history, ...sessionMessages], [history, sessionMessages]);

  const setSession = useCallback((target: number, updater: (items: ChatMessage[]) => ChatMessage[]) => {
    setSessions((prev) => ({ ...prev, [target]: updater(prev[target] ?? []) }));
  }, []);

  const append = useCallback(
    (target: number, message: ChatMessage) => setSession(target, (items) => [...items, message]),
    [setSession],
  );

  const replace = useCallback(
    (target: number, id: string, next: ChatMessage) =>
      setSession(target, (items) => items.map((item) => (item.id === id ? next : item))),
    [setSession],
  );

  const dropTrailingPair = useCallback(
    (target: number) =>
      setSession(target, (items) => {
        const copy = [...items];
        while (copy.length && copy[copy.length - 1]?.role === 'assistant') copy.pop();
        if (copy.length && copy[copy.length - 1]?.role === 'user') copy.pop();
        return copy;
      }),
    [setSession],
  );

  const requestAnswer = useCallback(
    async (conversationId: number, content: string, placeholderId: string, target: number) => {
      try {
        const { data } = await api.post<ChatAnswer>(`/chat/conversations/${conversationId}/messages`, {
          content,
        });
        replace(target, placeholderId, answerToMessage(data));
        void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
        void queryClient.invalidateQueries({ queryKey: queryKeys.conversation(String(conversationId)) });
      } catch (error) {
        replace(target, placeholderId, {
          id: placeholderId,
          role: 'assistant',
          content: apiErrorMessage(error, 'The answer could not be generated.'),
          created_at: new Date().toISOString(),
          error: true,
        });
      }
    },
    [queryClient, replace],
  );

  const send = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || sendingRef.current) return;
      sendingRef.current = true;
      setIsSending(true);

      const userMessage: ChatMessage = {
        id: localId('u'),
        role: 'user',
        content: trimmed,
        created_at: new Date().toISOString(),
      };
      const placeholder: ChatMessage = {
        id: localId('p'),
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
        pending: true,
      };

      append(key, userMessage);
      append(key, placeholder);

      let conversationId = activeId;
      let target = key;

      try {
        if (conversationId === null) {
          const { data } = await api.post<ConversationDto>('/chat/conversations', {});
          conversationId = data.id;
          target = conversationId;
          // Move the draft thread (stored under key 0) onto the new conversation.
          setSessions((prev) => {
            const { [0]: draft, ...rest } = prev;
            return { ...rest, [conversationId as number]: draft ?? [] };
          });
          setCreatedId(conversationId);
          void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
        }
        await requestAnswer(conversationId, trimmed, placeholder.id, target);
      } catch (error) {
        replace(target, placeholder.id, {
          id: placeholder.id,
          role: 'assistant',
          content: apiErrorMessage(error, 'Could not start the conversation.'),
          created_at: new Date().toISOString(),
          error: true,
        });
      } finally {
        sendingRef.current = false;
        setIsSending(false);
      }
    },
    [activeId, append, key, queryClient, replace, requestAnswer],
  );

  const retry = useCallback(
    async (assistantMessage: ChatMessage) => {
      if (sendingRef.current) return;
      const list = sessions[key] ?? [];
      const index = list.findIndex((item) => item.id === assistantMessage.id);
      if (index < 0) return;
      const priorUser = [...list.slice(0, index)].reverse().find((item) => item.role === 'user');
      if (!priorUser) return;

      // If the conversation never got created, replay the whole turn instead.
      if (activeId === null) {
        dropTrailingPair(key);
        await send(priorUser.content);
        return;
      }

      sendingRef.current = true;
      setIsSending(true);
      const placeholder: ChatMessage = {
        id: localId('p'),
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
        pending: true,
      };
      // Replace the failed answer in place, keeping the question visible.
      setSession(key, (items) => [...items.slice(0, index), placeholder]);
      await requestAnswer(activeId, priorUser.content, placeholder.id, key);
      sendingRef.current = false;
      setIsSending(false);
    },
    [activeId, dropTrailingPair, key, requestAnswer, send, sessions, setSession],
  );

  return {
    activeId,
    messages,
    isSending,
    isLoadingHistory: detail.isPending && activeId !== null,
    historyError: detail.error,
    send,
    retry,
  };
}
