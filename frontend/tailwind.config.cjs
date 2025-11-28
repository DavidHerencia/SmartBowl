module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        smart: {
          blue: "#2563eb",
          cyan: "#06b6d4"
        }
      },
      fontFamily: {
        display: ["Sora", "Inter", "system-ui", "sans-serif"]
      }
    }
  },
  plugins: []
};
