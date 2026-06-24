/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0a",
        surface: "#1a1a1a",
        border: "#2a2a2a",
        muted: "#888888",
        dim: "#555555",
        planner: "#3b82f6",
        thinking: "#a855f7",
        task: "#f97316",
        genui: "#22c55e",
        registry: "#14b8a6",
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      keyframes: {
        pulse: {
          "0%, 100%": { opacity: "0.35" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        pulse: "pulse 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
