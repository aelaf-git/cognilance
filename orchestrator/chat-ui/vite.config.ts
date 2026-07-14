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
    outDir: "../src/orchestrator/ui/static",
    // Keep .gitkeep; only replace index.html each build.
    emptyOutDir: false,
    cssCodeSplit: false,
  },
});
