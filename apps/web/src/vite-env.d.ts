/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the AgentShield control plane API. */
  readonly VITE_API_BASE_URL?: string;
  /** API key used to authenticate dashboard requests (dev convenience). */
  readonly VITE_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
