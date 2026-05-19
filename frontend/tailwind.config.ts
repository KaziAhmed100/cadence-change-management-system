import type { Config } from "tailwindcss";

/**
 * Cadence design tokens.
 *
 * Cherry + white is the brand palette. Everything visible to the user
 * should compose from these tokens rather than hardcoded hex values.
 * If you find yourself reaching for an arbitrary color, add it here first.
 */
const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand — crimson cherry on white
        cherry: {
          50: "#FFF0F3",
          100: "#FFE0E7",
          200: "#FFC2CF",
          300: "#FF94AC",
          400: "#FF5C7F",
          500: "#DC143C", // primary
          600: "#B8102F",
          700: "#940C24",
          800: "#70091B",
          900: "#4D0612",
        },
        // Surfaces
        canvas: "#FAFAF9", // app background
        surface: "#FFFFFF", // card backgrounds

        // Text
        ink: {
          primary: "#1F1F1F",
          secondary: "#64748B",
          muted: "#94A3B8",
        },

        // Status (used for change state, approval, SLA badges)
        status: {
          success: "#10B981",
          warning: "#F59E0B",
          danger: "#EF4444",
          info: "#3B82F6",
        },

        // Borders
        hairline: "#E5E7EB",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        // Soft elevation for cards — avoids the harsh default shadow look
        card: "0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px 0 rgba(0, 0, 0, 0.03)",
        "card-hover":
          "0 4px 6px -1px rgba(0, 0, 0, 0.06), 0 2px 4px -2px rgba(0, 0, 0, 0.04)",
      },
      borderRadius: {
        // We standardize on these to keep the UI consistent
        sm: "6px",
        DEFAULT: "8px",
        md: "10px",
        lg: "12px",
        xl: "16px",
      },
    },
  },
  plugins: [],
};

export default config;
