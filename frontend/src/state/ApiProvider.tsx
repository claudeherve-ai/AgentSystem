import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { ApiClient } from "../api/client";
import {
  createAuthProvider,
  readConfiguredAuthMode,
  type AuthProvider,
} from "../api/auth/authProvider";

export interface ApiContextValue {
  client: ApiClient;
  authProvider: AuthProvider;
  baseUrl: string;
}

const ApiContext = createContext<ApiContextValue | null>(null);

function resolveBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (configured && configured.trim()) return configured.trim();
  // Same-origin fallback keeps the app usable behind a reverse proxy that
  // serves both the SPA and the API without an explicit env var.
  return typeof window !== "undefined" ? window.location.origin : "";
}

export function ApiProvider({ children }: { children: ReactNode }) {
  const [value] = useState<ApiContextValue>(() => {
    const baseUrl = resolveBaseUrl();
    const authProvider = createAuthProvider(readConfiguredAuthMode());
    const client = new ApiClient({ baseUrl, authProvider });
    return { client, authProvider, baseUrl };
  });

  const memoized = useMemo(() => value, [value]);
  return <ApiContext.Provider value={memoized}>{children}</ApiContext.Provider>;
}

export function useApi(): ApiContextValue {
  const ctx = useContext(ApiContext);
  if (!ctx) throw new Error("useApi() must be used within <ApiProvider>");
  return ctx;
}
