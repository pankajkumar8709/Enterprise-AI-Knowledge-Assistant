import { create } from 'zustand';

export type ToastTone = 'success' | 'error' | 'info';

export interface ToastItem {
  id: string;
  tone: ToastTone;
  title: string;
  description?: string;
}

interface UiStore {
  toasts: ToastItem[];
  pushToast: (toast: Omit<ToastItem, 'id'>) => string;
  dismissToast: (id: string) => void;
  /** Icon-rail / drawer state for viewports below `lg`. */
  navOpen: boolean;
  setNavOpen: (open: boolean) => void;
  toggleNav: () => void;
}

let toastSeq = 0;

export const useUiStore = create<UiStore>((set) => ({
  toasts: [],

  pushToast(toast) {
    toastSeq += 1;
    const id = `t${toastSeq}`;
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }].slice(-4) }));
    return id;
  },

  dismissToast(id) {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },

  navOpen: false,
  setNavOpen: (open) => set({ navOpen: open }),
  toggleNav: () => set((state) => ({ navOpen: !state.navOpen })),
}));

/**
 * Imperative toast helper for use outside React (query hooks, error handlers).
 * All failures surface `ApiError.error.message`.
 */
export const toast = {
  success: (title: string, description?: string) =>
    useUiStore.getState().pushToast({ tone: 'success', title, ...(description ? { description } : {}) }),
  error: (title: string, description?: string) =>
    useUiStore.getState().pushToast({ tone: 'error', title, ...(description ? { description } : {}) }),
  info: (title: string, description?: string) =>
    useUiStore.getState().pushToast({ tone: 'info', title, ...(description ? { description } : {}) }),
};
