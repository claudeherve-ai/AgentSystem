import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Node's built-in fetch/ReadableStream/TextEncoder/TextDecoder are available
// globally under Vitest (Node 18+), so no polyfills are required here. This
// file exists as the single place to add global test setup as needed.
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
