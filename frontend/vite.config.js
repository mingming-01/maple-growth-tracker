import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

const frontendRoot = fileURLToPath(new URL(".", import.meta.url));
const previewOutput = fileURLToPath(new URL("../static/react-preview/", import.meta.url));

export default defineConfig({
  root: frontendRoot,
  plugins: [react()],
  base: "/static/react-preview/",
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.FLASK_API_PROXY_TARGET || "http://127.0.0.1:5000",
        changeOrigin: true
      },
      "/static": {
        target: process.env.FLASK_API_PROXY_TARGET || "http://127.0.0.1:5000",
        changeOrigin: true
      },
      "/admin": {
        target: process.env.FLASK_API_PROXY_TARGET || "http://127.0.0.1:5000",
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: previewOutput,
    emptyOutDir: true,
    sourcemap: false
  }
});