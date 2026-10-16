import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, proxy API calls to the Django backend (python manage.py runserver).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.VITE_PROXY_TARGET || "http://localhost:8000",
    },
  },
});
