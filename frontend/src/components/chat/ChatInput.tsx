import { Send } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';

const MAX_LENGTH = 2000;
const COUNTER_THRESHOLD = 1800;
const MAX_ROWS = 6;
const LINE_HEIGHT_PX = 24; // text-sm leading-6

export interface ChatInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
  /** Value injected when a suggestion card is chosen. */
  initialValue?: string;
}

/** Sticky composer: Enter sends, Shift+Enter adds a newline (spec §12.2.3). */
export function ChatInput({ onSend, disabled = false, placeholder = 'Ask about a policy, a person or a process…', initialValue }: ChatInputProps) {
  const [value, setValue] = useState(initialValue ?? '');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (initialValue !== undefined) setValue(initialValue);
  }, [initialValue]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const max = LINE_HEIGHT_PX * MAX_ROWS + 20;
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
    el.style.overflowY = el.scrollHeight > max ? 'auto' : 'hidden';
  }, [value]);

  function submit(): void {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
  }

  const tooLong = value.length > MAX_LENGTH;

  return (
    <form
      className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm transition focus-within:border-indigo-300"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label htmlFor="chat-input" className="sr-only">
        Ask a question
      </label>
      <textarea
        id="chat-input"
        ref={textareaRef}
        rows={1}
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        aria-describedby={value.length >= COUNTER_THRESHOLD ? 'chat-input-counter' : undefined}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        className="focus-ring max-h-40 w-full resize-none rounded-xl border-0 bg-transparent px-2 py-2 text-sm leading-6 text-slate-900 placeholder:text-slate-400 focus-visible:outline-none disabled:text-slate-400"
      />
      <div className="mt-1 flex items-center justify-between gap-3 px-1">
        <p className="text-[11px] text-slate-400">
          <kbd className="rounded border border-slate-200 bg-slate-50 px-1 py-0.5 font-sans text-[10px]">Enter</kbd> to
          send · <kbd className="rounded border border-slate-200 bg-slate-50 px-1 py-0.5 font-sans text-[10px]">Shift</kbd>
          +<kbd className="rounded border border-slate-200 bg-slate-50 px-1 py-0.5 font-sans text-[10px]">Enter</kbd> for a
          new line
        </p>
        <div className="flex items-center gap-3">
          {value.length >= COUNTER_THRESHOLD ? (
            <span
              id="chat-input-counter"
              className={cn('text-[11px] tabular-nums', tooLong ? 'text-rose-600' : 'text-slate-500')}
            >
              {value.length}/{MAX_LENGTH}
            </span>
          ) : null}
          <Button
            type="submit"
            size="sm"
            disabled={disabled || !value.trim() || tooLong}
            aria-label="Send question"
            icon={<Send aria-hidden="true" className="h-3.5 w-3.5" />}
          >
            Send
          </Button>
        </div>
      </div>
    </form>
  );
}
