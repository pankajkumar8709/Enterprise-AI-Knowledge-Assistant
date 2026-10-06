import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';
import { useEffect, type ReactNode } from 'react';

import { cn } from '@/lib/cn';
import { useUiStore, type ToastItem, type ToastTone } from '@/store/uiStore';

const TONES: Record<ToastTone, { icon: ReactNode; className: string }> = {
  success: {
    icon: <CheckCircle2 aria-hidden="true" className="h-4 w-4 text-emerald-600" />,
    className: 'border-emerald-200 bg-white',
  },
  error: {
    icon: <AlertTriangle aria-hidden="true" className="h-4 w-4 text-rose-600" />,
    className: 'border-rose-200 bg-white',
  },
  info: {
    icon: <Info aria-hidden="true" className="h-4 w-4 text-sky-600" />,
    className: 'border-slate-200 bg-white',
  },
};

function ToastCard({ item }: { item: ToastItem }) {
  const dismiss = useUiStore((s) => s.dismissToast);
  const tone = TONES[item.tone];

  useEffect(() => {
    const timer = window.setTimeout(() => dismiss(item.id), item.tone === 'error' ? 7000 : 4500);
    return () => window.clearTimeout(timer);
  }, [dismiss, item.id, item.tone]);

  return (
    <div
      role={item.tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'pointer-events-auto flex w-full max-w-sm animate-fade-in items-start gap-3 rounded-xl border p-3 shadow-lg',
        tone.className,
      )}
    >
      <span className="mt-0.5">{tone.icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-slate-900">{item.title}</p>
        {item.description ? <p className="mt-0.5 text-xs leading-5 text-slate-500">{item.description}</p> : null}
      </div>
      <button
        type="button"
        onClick={() => dismiss(item.id)}
        aria-label="Dismiss notification"
        className="focus-ring -mr-1 shrink-0 rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
      >
        <X aria-hidden="true" className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/** Mount once in the app shell; announcements are polite so they don't interrupt typing. */
export function Toaster() {
  const toasts = useUiStore((s) => s.toasts);
  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2"
    >
      {toasts.map((item) => (
        <ToastCard key={item.id} item={item} />
      ))}
    </div>
  );
}
