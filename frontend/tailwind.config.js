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
          DEFAULT: "#E8E4D3", // Warm Ivory
          alt: "#DFDBCA",     // Section contrast
          elevated: "#F4F1E6",
        },
        ink: {
          DEFAULT: "#031211", // Ink Black
          secondary: "#5C584E",
          muted: "#9E988A",
        },
        accent: {
          DEFAULT: "#00AEBB", // Electric Teal
          hover: "#008E99",
          soft: "rgba(0, 174, 187, 0.15)",
        },
        border: {
          DEFAULT: "#D8D3C3",
          subtle: "#E0DCCC",
          emphasis: "rgba(3, 18, 17, 0.1)",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        serif: ["Newsreader", "Playfair Display", "Georgia", "serif"],
        mono: ["JetBrains Mono", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

