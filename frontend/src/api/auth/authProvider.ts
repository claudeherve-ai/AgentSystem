/**
 * Auth-provider abstraction.
 *
 * The backend supports three real auth modes (`agentsystem/services/identity.py`):
 *   - api_key    — a static operator key sent as `Authorization: Bearer <key>`
 *   - easy_auth  — Azure App Service Easy Auth; same-origin cookies, no
 *                  bearer header, the frontend just needs `credentials: "include"`
 *   - entra_jwt  — a real Entra-issued access token as a bearer header
 *
 * We never fabricate a client id, tenant id, or token — for `entra_bearer`
 * mode this module only exposes an *extension point* (`configureEntraTokenProvider`)
 * that a real deployment wires up to its own MSAL/OAuth integration. Until
 * that's wired up, `configured` stays `false` and the UI shows an honest
 * "authentication not configured" banner instead of silently sending
 * unauthenticated requests.
 */

export type AuthMode = "none" | "api_key" | "easy_auth" | "entra_bearer";

export interface AuthRequestContext {
  headers: Record<string, string>;
  credentials?: RequestCredentials;
}

export interface AuthProvider {
  readonly mode: AuthMode;
  /** Whether this provider currently has what it needs to authenticate. */
  isConfigured(): boolean;
  /** Human-readable explanation shown in "not configured" banners. */
  describe(): string;
  getRequestContext(): Promise<AuthRequestContext>;
  /** Optional: subscribe to configuration changes (key set/cleared, etc.). */
  subscribe?(listener: () => void): () => void;
}

const API_KEY_STORAGE_KEY = "agentsystem.auth.apiKey";

/**
 * Local operator API key, held only in `sessionStorage` (cleared when the
 * tab closes) — deliberately not `localStorage`, since the task scopes
 * persisted preferences to "harmless" values and a secret key doesn't
 * qualify.
 */
export class ApiKeyAuthProvider implements AuthProvider {
  readonly mode: AuthMode = "api_key";
  private listeners = new Set<() => void>();

  getKey(): string | null {
    try {
      return sessionStorage.getItem(API_KEY_STORAGE_KEY);
    } catch {
      return null;
    }
  }

  setKey(key: string): void {
    try {
      sessionStorage.setItem(API_KEY_STORAGE_KEY, key);
    } catch {
      // Storage unavailable (private mode, etc.) — key just won't persist.
    }
    this.emit();
  }

  clearKey(): void {
    try {
      sessionStorage.removeItem(API_KEY_STORAGE_KEY);
    } catch {
      // no-op
    }
    this.emit();
  }

  isConfigured(): boolean {
    return Boolean(this.getKey());
  }

  describe(): string {
    return this.isConfigured()
      ? "Using a locally-stored API key for this session."
      : "No API key set — enter one to authenticate requests.";
  }

  async getRequestContext(): Promise<AuthRequestContext> {
    const key = this.getKey();
    return key ? { headers: { Authorization: `Bearer ${key}` } } : { headers: {} };
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(): void {
    for (const listener of this.listeners) listener();
  }
}

/** Same-origin Azure App Service Easy Auth: rely on the session cookie. */
export class EasyAuthProvider implements AuthProvider {
  readonly mode: AuthMode = "easy_auth";

  isConfigured(): boolean {
    return true;
  }

  describe(): string {
    return "Using same-origin Easy Auth session cookies.";
  }

  async getRequestContext(): Promise<AuthRequestContext> {
    return { headers: {}, credentials: "include" };
  }
}

export type EntraTokenProvider = () => Promise<string | null>;

let entraTokenProvider: EntraTokenProvider | null = null;

/**
 * Wire a real token-acquisition callback (e.g. from your MSAL instance) for
 * `entra_bearer` mode. Deliberately not configured by default.
 */
export function configureEntraTokenProvider(provider: EntraTokenProvider | null): void {
  entraTokenProvider = provider;
}

/** Entra ID bearer tokens, sourced from an externally-registered provider. */
export class EntraBearerAuthProvider implements AuthProvider {
  readonly mode: AuthMode = "entra_bearer";

  isConfigured(): boolean {
    return entraTokenProvider !== null;
  }

  describe(): string {
    return this.isConfigured()
      ? "Using a bearer token supplied by the configured Entra token provider."
      : "No Entra token provider is registered. Call configureEntraTokenProvider() " +
          "with your MSAL/OAuth integration to enable Entra authentication.";
  }

  async getRequestContext(): Promise<AuthRequestContext> {
    if (!entraTokenProvider) return { headers: {} };
    const token = await entraTokenProvider();
    return token ? { headers: { Authorization: `Bearer ${token}` } } : { headers: {} };
  }
}

/** No authentication attached — used when the server has auth disabled. */
export class NoAuthProvider implements AuthProvider {
  readonly mode: AuthMode = "none";
  isConfigured(): boolean {
    return true;
  }
  describe(): string {
    return "No authentication configured; requests are sent unauthenticated.";
  }
  async getRequestContext(): Promise<AuthRequestContext> {
    return { headers: {} };
  }
}

export function createAuthProvider(mode: AuthMode): AuthProvider {
  switch (mode) {
    case "api_key":
      return new ApiKeyAuthProvider();
    case "easy_auth":
      return new EasyAuthProvider();
    case "entra_bearer":
      return new EntraBearerAuthProvider();
    case "none":
    default:
      return new NoAuthProvider();
  }
}

export function readConfiguredAuthMode(): AuthMode {
  const raw = import.meta.env.VITE_AUTH_MODE;
  if (raw === "api_key" || raw === "easy_auth" || raw === "entra_bearer" || raw === "none") {
    return raw;
  }
  return "none";
}
