/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// AgentSystem mission-control frontend build/test configuration.
// Kept intentionally small: one plugin, one env prefix, one test environment.
export default defineConfig({
  plugins: [react()],
  envPrefix: "VITE_",
  build: {
    target: "es2022",
    sourcemap: true,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8080",
      "/health": "http://127.0.0.1:8080",
      "/readiness": "http://127.0.0.1:8080",
      "/live": "http://127.0.0.1:8080",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    css: false,
    restoreMocks: true,
    clearMocks: true,
  },
});
