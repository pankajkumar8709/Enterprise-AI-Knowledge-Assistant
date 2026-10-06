import { useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { ChatWindow } from '@/components/chat/ChatWindow';
import { ROUTES } from '@/lib/constants';

/** `/app/chat` and `/app/chat/:conversationId` (spec §12.2). */
export function ChatPage() {
  const params = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();

  const parsed = params.conversationId ? Number(params.conversationId) : NaN;
  const conversationId = Number.isFinite(parsed) ? parsed : null;

  const handleSelect = useCallback(
    (id: number | null) => {
      navigate(id === null ? ROUTES.chat : `${ROUTES.chat}/${id}`, { replace: false });
    },
    [navigate],
  );

  return <ChatWindow conversationId={conversationId} onSelectConversation={handleSelect} />;
}
