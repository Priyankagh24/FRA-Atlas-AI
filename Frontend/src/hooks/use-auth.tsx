import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

type AuthUser = {
  id: string;
  email: string;
};

type AuthContextValue = {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const AUTH_STORAGE_KEY = "fra_auth_user_v1";

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(AUTH_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as AuthUser;
        if (parsed?.email) setUser(parsed);
      }
    } catch {
      // ignore parse errors
    }
  }, []);

  const persistUser = useCallback((u: AuthUser | null) => {
    if (u) localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(u));
    else localStorage.removeItem(AUTH_STORAGE_KEY);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    // Fake auth: accept any non-empty values
    if (!email || !password) throw new Error("Email and password are required");
    const u: AuthUser = { id: crypto.randomUUID(), email };
    setUser(u);
    persistUser(u);
  }, [persistUser]);

  const signup = useCallback(async (email: string, password: string) => {
    if (!email || !password) throw new Error("Email and password are required");
    const u: AuthUser = { id: crypto.randomUUID(), email };
    setUser(u);
    persistUser(u);
  }, [persistUser]);

  const logout = useCallback(() => {
    setUser(null);
    persistUser(null);
  }, [persistUser]);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    isAuthenticated: Boolean(user),
    login,
    signup,
    logout,
  }), [user, login, signup, logout]);

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextValue => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};


