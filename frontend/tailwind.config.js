/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0f172a", // Darker slate surface
        ink: "#f8fafc",      // White ink for deep environments
        brand: "#38bdf8",    // Vibrant neon sky blue
        brand2: "#818cf8",   // Indigo accent
        accent: "#10b981",   // Emerald neon
        warn: "#fbbf24",
        "glass-border": "rgba(255, 255, 255, 0.08)",
        "glass-panel": "rgba(30, 41, 59, 0.6)",
      },
      fontFamily: {
        sans: ["'DM Sans'", "system-ui", "sans-serif"],
        display: ["'Outfit'", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 8px 32px 0 rgba(0, 0, 0, 0.36)",
        glow: "0 0 20px 0 rgba(56, 189, 248, 0.3)",
      },
      keyframes: {
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-glow": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        shimmer: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
        "fade-in-blur": {
          from: { opacity: "0", filter: "blur(10px)" },
          to: { opacity: "1", filter: "blur(0px)" },
        },
      },
      animation: {
        "slide-up": "slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "pulse-glow": "pulse-glow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "shimmer": "shimmer 2s infinite linear",
        "fade-in-blur": "fade-in-blur 0.5s ease-out forwards",
      },
    },
  },
  plugins: [],
};
