import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/voice-note": "http://localhost:8000",
      "/realtime": "http://localhost:8000",
      "/auth": "http://localhost:8000",
    },
  },
});
