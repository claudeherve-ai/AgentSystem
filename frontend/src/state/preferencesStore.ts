import { createLocalStore } from "./localStore";

export type ComposerMode = "auto" | "specific";
export type MotionPreference = "system" | "reduced" | "full";

export interface UiPreferences {
  composerMode: ComposerMode;
  motion: MotionPreference;
  navCollapsed: boolean;
  transcriptWordWrap: boolean;
}

const DEFAULT_PREFERENCES: UiPreferences = {
  composerMode: "auto",
  motion: "system",
  navCollapsed: false,
  transcriptWordWrap: true,
};

export const preferencesStore = createLocalStore<UiPreferences>(
  "agentsystem.ui.preferences",
  DEFAULT_PREFERENCES,
);
