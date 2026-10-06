import { useEffect } from 'react';

import { useAuthStore, type SignupInput } from '@/store/authStore';
import type { Role, User } from '@/types/api';

export interface UseAuthResult {
  user: User | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  bootstrapping: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (input: SignupInput) => Promise<User>;
  logout: () => Promise<void>;
  hasRole: (role: Role) => boolean;
}

export function useAuth(): UseAuthResult {
  const user = useAuthStore((s) => s.user);
  const bootstrapping = useAuthStore((s) => s.bootstrapping);
  const login = useAuthStore((s) => s.login);
  const signup = useAuthStore((s) => s.signup);
  const logout = useAuthStore((s) => s.logout);
  const hasRole = useAuthStore((s) => s.hasRole);

  return {
    user,
    isAuthenticated: Boolean(user),
    isAdmin: user?.role === 'admin',
    bootstrapping,
    login,
    signup,
    logout,
    hasRole,
  };
}

/** Resolve the persisted session once at app start (`GET /auth/me`). */
export function useBootstrapAuth(): void {
  const loadMe = useAuthStore((s) => s.loadMe);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);
}
