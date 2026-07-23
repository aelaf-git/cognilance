import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";
import path from "path";

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "../src/agent_host/static",
    // Keep brand assets (logo.png / icon.png) that live alongside the SPA.
    emptyOutDir: false,
    cssCodeSplit: false,
  },
});
