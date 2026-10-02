import { useSyncExternalStore } from "react";
import type { LocalStore } from "../state/localStore";

/** Subscribes a component to a `LocalStore`, re-rendering on any change. */
export function useLocalStore<T>(store: LocalStore<T>): T {
  return useSyncExternalStore(store.subscribe, store.get, store.get);
}
