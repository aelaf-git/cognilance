/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0e0918",
        surface: "#1a1624",
        border: "#2c2834",
        muted: "#c9c5c5",
        dim: "#9d9797",
        ember: "#ff492c",
        "ember-soft": "#fd8925",
        planner: "#fd8925",
        thinking: "#ff8e5d",
        task: "#ff492c",
        genui: "#fd8925",
        registry: "#ff492c",
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "-apple-system", "sans-serif"],
        display: ['"Space Grotesk"', "system-ui", "sans-serif"],
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
