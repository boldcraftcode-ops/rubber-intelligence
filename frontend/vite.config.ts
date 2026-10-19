import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Frontend dev memanggil API lewat proxy satu-origin (/api -> backend
// di 127.0.0.1), sehingga kode browser tidak pernah memakai localhost.
// Port bisa diatur lewat variabel lingkungan tanpa mengubah kode:
//   PORT     = port tampilan web (default 5173)
//   API_PORT = port backend yang diproksi (default 8000)
const portWeb = Number(process.env.PORT ?? 5173);
const portApi = Number(process.env.API_PORT ?? 8000);

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: portWeb,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      "/api": { target: `http://127.0.0.1:${portApi}`, changeOrigin: true },
    },
  },
});
