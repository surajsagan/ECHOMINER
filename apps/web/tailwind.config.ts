import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "var(--em-ink)",
        deep: "var(--em-deep)",
        teal: "var(--em-teal)",
        mist: "var(--em-mist)",
        line: "var(--em-line)",
        alert: "var(--em-alert)",
        paper: "var(--em-paper)",
        muted: "var(--em-muted)",
      },
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
        mono: ["var(--font-mono)"],
      },
      maxWidth: { content: "72rem" },
    },
  },
  plugins: [],
};
export default config;
