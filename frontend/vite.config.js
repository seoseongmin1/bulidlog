import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발할 때는 화면(5173)이 서버(8000)의 /api를 대신 불러 준다.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.js",
  },
});
