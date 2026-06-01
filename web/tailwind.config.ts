import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: "hsl(var(--card))",
        muted: "hsl(var(--muted))",
        "muted-foreground": "hsl(var(--muted-foreground))",
        primary: "hsl(var(--primary))",
        up: "#089981",
        down: "#f23645",
        amber: "#f7931a",
        accent: "#22d3ee",
      },
      borderRadius: { lg: "8px", md: "6px", sm: "4px" },
      fontFamily: { sans: ["Trebuchet MS", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
export default config;
