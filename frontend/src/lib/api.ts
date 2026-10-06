import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

import type { ApiError } from '@/types/api';

/** Default is same-origin `/api/v1`, which works with the Vite dev proxy and a reverse proxy. */
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1';

export const api = axios.create({ baseURL: API_BASE_URL, timeout: 70_000 });

interface AuthHandlers {
  getToken: () => string | null;
  /** Rotate the refresh token and resolve with a fresh access token. */
  refresh: () => Promise<string>;
  /** Called when refresh is impossible: clear auth state and go to /login?expired=1. */
  onRefreshFailed: () => void;
}

/**
 * The auth store registers these handlers on module load. Keeping the store out of
 * this module avoids a circular import while still letting interceptors read live state.
 */
let handlers: AuthHandlers | null = null;

export function registerAuthHandlers(next: AuthHandlers): void {
  handlers = next;
}

api.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  const token = handlers?.getToken();
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

/** In-flight refresh shared by all concurrent 401s (refresh exactly once). */
let refreshing: Promise<string> | null = null;

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const auth = handlers;
    const isAuthCall = original?.url?.includes('/auth/') ?? false;

    if (error.response?.status === 401 && original && auth && !original._retry && !isAuthCall) {
      original._retry = true;
      try {
        refreshing ??= auth.refresh().finally(() => {
          refreshing = null;
        });
        const token = await refreshing;
        original.headers.Authorization = `Bearer ${token}`;
        return await api(original);
      } catch {
        auth.onRefreshFailed();
        if (!window.location.pathname.startsWith('/login')) {
          window.location.assign('/login?expired=1');
        }
      }
    }
    return Promise.reject(error);
  },
);

function isApiErrorBody(value: unknown): value is ApiError {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = (value as { error?: unknown }).error;
  if (typeof candidate !== 'object' || candidate === null) return false;
  return typeof (candidate as { message?: unknown }).message === 'string';
}

/** Human-readable message for any thrown request error, preferring `error.message`. */
export function apiErrorMessage(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ECONNABORTED') return 'The request timed out. Please try again.';
    if (!error.response) return 'Cannot reach the server. Check your connection and try again.';
    if (isApiErrorBody(error.response.data)) return error.response.data.error.message || fallback;
    if (error.response.status >= 500) return 'The server had a problem. Please try again.';
    return error.message || fallback;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}

/** The `error.code` from the API contract, or null for non-API failures. */
export function apiErrorCode(error: unknown): string | null {
  if (axios.isAxiosError(error) && isApiErrorBody(error.response?.data)) {
    return error.response.data.error.code;
  }
  return null;
}

/** Fetch a protected file and hand it to the browser as a download. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const response = await api.get<Blob>(path, { responseType: 'blob' });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
