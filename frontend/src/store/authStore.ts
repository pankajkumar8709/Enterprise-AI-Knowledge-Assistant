import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { api, registerAuthHandlers } from '@/lib/api';
import { toast } from '@/store/uiStore';
import type { Role, TokenPair, User } from '@/types/api';

export interface SignupInput {
  email: string;
  full_name: string;
  password: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  /** True while the initial `GET /auth/me` is unresolved. */
  bootstrapping: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (input: SignupInput) => Promise<User>;
  refresh: () => Promise<string>;
  logout: () => Promise<void>;
  loadMe: () => Promise<User | null>;
  clearAuth: () => void;
  hasRole: (role: Role) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      bootstrapping: true,

      async login(email, password) {
        const { data } = await api.post<TokenPair>('/auth/login', { email, password });
        set({ accessToken: data.access_token, refreshToken: data.refresh_token });
        // The login payload carries a trimmed user (no department/is_active),
        // so always hydrate the full profile from GET /auth/me.
        const user = await fetchMe(data.access_token);
        set({ user, bootstrapping: false });
        return user;
      },

      async signup(input) {
        // `POST /auth/signup` returns the created User (role is always employee).
        await api.post<User>('/auth/signup', input);
        return get().login(input.email, input.password);
      },

      async refresh() {
        const token = get().refreshToken;
        if (!token) throw new Error('No refresh token available');
        // Refresh-token rotation: the old token is revoked, both tokens are replaced.
        const { data } = await api.post<TokenPair>('/auth/refresh', { refresh_token: token });
        // The refresh payload carries a trimmed user, so keep the full profile we already have.
        set({ accessToken: data.access_token, refreshToken: data.refresh_token });
        return data.access_token;
      },

      async logout() {
        const token = get().refreshToken;
        if (token) {
          try {
            await api.post('/auth/logout', { refresh_token: token });
          } catch {
            // Logging out locally must succeed even if revocation fails.
          }
        }
        get().clearAuth();
      },

      async loadMe() {
        const token = get().accessToken;
        if (!token) {
          set({ bootstrapping: false });
          return null;
        }
        try {
          const { data } = await api.get<User>('/auth/me');
          set({ user: data, bootstrapping: false });
          return data;
        } catch {
          set({ user: null, accessToken: null, refreshToken: null, bootstrapping: false });
          return null;
        }
      },

      clearAuth() {
        set({ user: null, accessToken: null, refreshToken: null, bootstrapping: false });
      },

      hasRole(role) {
        return get().user?.role === role;
      },
    }),
    {
      name: 'kb-auth',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    },
  ),
);

async function fetchMe(accessToken: string): Promise<User> {
  const { data } = await api.get<User>('/auth/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return data;
}

// Wire the axios interceptors to this store's live state (see lib/api.ts for why).
registerAuthHandlers({
  getToken: () => useAuthStore.getState().accessToken,
  refresh: () => useAuthStore.getState().refresh(),
  // Refresh failed → drop the session; lib/api.ts sends the browser to /login?expired=1.
  onRefreshFailed: () => {
    useAuthStore.getState().clearAuth();
    toast.error('Session expired', 'Please sign in again.');
  },
});
