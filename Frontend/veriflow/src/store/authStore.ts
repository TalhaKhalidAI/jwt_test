import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface User {
  id: string | number;
  email: string;
  name?: string;
  role?: string;
  user_role?: string;
  permissions?: Record<string, boolean>;
  profile_pic?: string;
  is_active?: boolean;
  mfa_enabled?: boolean;
  mfa_method?: string | null;
}

export interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  setAuth: (
    arg1: User | string,
    arg2?: string | null,
    arg3?: User | string | null
  ) => void;
  setUser: (user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      setAuth: (arg1, arg2, arg3) => {
        if (typeof arg1 === 'string') {
          // called as setAuth(token, refreshToken, user)
          set({
            token: arg1,
            refreshToken: typeof arg2 === 'string' ? arg2 : null,
            user: typeof arg3 === 'object' && arg3 ? (arg3 as User) : null,
            isAuthenticated: true,
          });
        } else {
          // called as setAuth(user, token?, refreshToken?)
          set((state) => ({
            user: {
              ...arg1,
              role: arg1.role || arg1.user_role || 'worker',
              user_role: arg1.user_role || arg1.role || 'worker',
            },
            isAuthenticated: true,
            token: typeof arg2 === 'string' ? arg2 : state.token,
            refreshToken: typeof arg3 === 'string' ? arg3 : state.refreshToken,
          }));
        }
      },
      setUser: (user) => {
        set({
          user: {
            ...user,
            role: user.role || user.user_role || 'worker',
            user_role: user.user_role || user.role || 'worker',
          },
          isAuthenticated: true,
        });
      },
      logout: () => {
        set({ token: null, refreshToken: null, user: null, isAuthenticated: false });
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
