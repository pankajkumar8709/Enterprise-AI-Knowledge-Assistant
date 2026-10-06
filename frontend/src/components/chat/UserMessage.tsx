import { formatDateTime } from '@/lib/format';
import type { ChatMessage } from '@/types/api';

export function UserMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-end">
      <div className="flex max-w-[85%] flex-col items-end gap-1">
        <div className="whitespace-pre-wrap rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-sm leading-6 text-white shadow-sm">
          {message.content}
        </div>
        <span className="text-[11px] text-slate-400">{formatDateTime(message.created_at)}</span>
      </div>
    </div>
  );
}
