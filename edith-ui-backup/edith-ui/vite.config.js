import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],

  // Vite generates relative asset paths so Python can
  // load the production build directly from the filesystem.
  base: "./",
});