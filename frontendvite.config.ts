import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // O backend expÃµe as rotas na raiz (/documents, /dashboard); em dev o front
      // usa o prefixo /api, entÃ£o removemos /api ao encaminhar pro backend.
      "/api": {
        target: "https://urldefense.com/v3/__http://localhost:8000__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczu08MFM3$ ",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
