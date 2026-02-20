import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

function normalizeBasePath(pathValue?: string): string {
  if (!pathValue) {
    return "/";
  }

  let normalized = pathValue.trim();
  if (!normalized) {
    return "/";
  }
  if (!normalized.startsWith("/")) {
    normalized = `/${normalized}`;
  }
  if (!normalized.endsWith("/")) {
    normalized = `${normalized}/`;
  }
  return normalized;
}

export default defineConfig({
  base: normalizeBasePath(process.env.VITE_BASE_PATH),
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
