import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: false,
    allowedHosts: [
      "localhost",
      "127.0.0.1",
      "gave-doctor-laws-interviews.trycloudflare.com",
      "costume-cotton-condition-cheaper.trycloudflare.com",
      ".trycloudflare.com",
    ],
  },
});
