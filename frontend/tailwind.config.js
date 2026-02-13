const { heroui } = require("@heroui/react");

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    "./node_modules/@heroui/theme/dist/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [
    heroui({
      layout: {
        radius: {
          small: "8px",
          medium: "12px",
          large: "16px",
        },
        borderWidth: {
          small: "0.5px",
          medium: "1px",
          large: "1.5px",
        },
      },
    }),
  ],
}
