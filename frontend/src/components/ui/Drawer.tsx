import { X } from 'lucide-react';
import { useCallback, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

import { cn } from '@/lib/cn';

import { useFocusTrap, useLockBodyScroll } from './overlay';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  /** Panel width from `sm` up; full width on mobile. */
  widthClassName?: string;
  side?: 'right' | 'left';
  className?: string;
}

export function Drawer({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  widthClassName = 'sm:w-[420px]',
  side = 'right',
  className,
}: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const handleEscape = useCallback(() => onClose(), [onClose]);

  useLockBodyScroll(open);
  useFocusTrap(panelRef, open, handleEscape);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-slate-900/40" aria-hidden="true" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        className={cn(
          'relative z-10 flex h-full w-full flex-col bg-white shadow-xl',
          widthClassName,
          side === 'right' ? 'ml-auto animate-slide-in-right' : 'mr-auto',
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
          <div className="min-w-0">
            <h2 id="drawer-title" className="truncate text-base font-semibold text-slate-900">
              {title}
            </h2>
            {description ? <p className="mt-0.5 text-xs text-slate-500">{description}</p> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            className="focus-ring -mr-1 shrink-0 rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>
        <div className="thin-scrollbar flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer ? (
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 px-5 py-4">{footer}</div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
