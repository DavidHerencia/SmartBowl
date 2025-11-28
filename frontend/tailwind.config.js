/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        smart: {
          blue: "#2563eb",
          cyan: "#06b6d4",
          navy: "#0f172a"
        }
      },
      fontFamily: {
        display: ["Sora", "Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"]
      },
      boxShadow: {
        glow: "0 25px 45px -15px rgba(37, 99, 235, 0.35)"
      }
    }
  },
  plugins: []
};
