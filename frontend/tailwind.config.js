/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { 950: "#07111f", 900: "#0b1727", 850: "#0e1c2e", 800: "#122238" },
        accent: { 400: "#49d6b3", 500: "#27bd9a" }
      }
    }
  },
  plugins: []
};
