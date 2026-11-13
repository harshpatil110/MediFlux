/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: {
          DEFAULT: "var(--canvas, #E8E4D3)",
          alt: "var(--canvas-alt, #DFDBCA)",
          elevated: "var(--canvas-elevated, #F4F1E6)",
        },
        surface: {
          DEFAULT: "var(--surface, #FFFFFF)",
          elevated: "var(--surface-elevated, #F4F1E6)",
          muted: "var(--surface-muted, #E8E4D3)",
        },
        ink: {
          DEFAULT: "var(--ink, #031211)",
          secondary: "var(--ink-secondary, #5C584E)",
          muted: "var(--ink-muted, #9E988A)",
        },
        accent: {
          DEFAULT: "#00AEBB",
          hover: "#008E99",
          soft: "rgba(0, 174, 187, 0.15)",
        },
        border: {
          DEFAULT: "var(--border, #D8D3C3)",
          subtle: "var(--border-subtle, #E0DCCC)",
          emphasis: "var(--border-emphasis, rgba(3, 18, 17, 0.1))",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        serif: ["Playfair Display", "DM Serif Display", "Lora", "Georgia", "serif"],
        mono: ["JetBrains Mono", "Fira Code", "Menlo", "monospace"],
      },
      boxShadow: {
        sm: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
      },
      borderRadius: {
        sm: "2px",
        DEFAULT: "4px",
        md: "6px",
        lg: "8px",
        xl: "12px",
      },
    },
  },
  plugins: [],
};
