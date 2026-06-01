import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // dev proxy: forward data calls to the bot's aiohttp server
    proxy: {
      "/api": "http://localhost:8080",
      "/chart.png": "http://localhost:8080",
      "/health": "http://localhost:8080",
    },
  },
  test: { environment: "node" },
});
