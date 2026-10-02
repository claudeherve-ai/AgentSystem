/**
 * Minimal localStorage-backed store factory.
 *
 * Used only for the "harmless UI preferences and active workspace" data the
 * task explicitly allows in localStorage — never for secrets or server
 * state. Cross-tab updates are picked up via the `storage` event so two
 * open tabs stay in sync.
 */

export interface LocalStore<T> {
  get(): T;
  set(next: T | ((prev: T) => T)): void;
  subscribe(listener: () => void): () => void;
}

export function createLocalStore<T>(key: string, initial: T): LocalStore<T> {
  const listeners = new Set<() => void>();

  const readRaw = (): T => {
    try {
      const raw = window.localStorage.getItem(key);
      if (!raw) return initial;
      return { ...initial, ...(JSON.parse(raw) as Partial<T>) };
    } catch {
      return initial;
    }
  };

  let cached = readRaw();

  const writeRaw = (value: T): void => {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Storage unavailable (private mode/quota) — state stays in-memory
      // for this session, which is an acceptable degradation for prefs.
    }
  };

  if (typeof window !== "undefined") {
    window.addEventListener("storage", (event) => {
      if (event.key !== key) return;
      cached = readRaw();
      listeners.forEach((listener) => listener());
    });
  }

  return {
    get: () => cached,
    set: (next) => {
      cached = typeof next === "function" ? (next as (prev: T) => T)(cached) : next;
      writeRaw(cached);
      listeners.forEach((listener) => listener());
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
