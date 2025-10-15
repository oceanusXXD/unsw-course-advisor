/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx,css}"
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#0ea5a4',
          dark: '#059669',
          soft: '#16b0b0',
        },
        bg: {
          base: '#0b0e14',
          surface: '#0f131b',
          card: '#121826',
        },
        text: {
          primary: '#e5e7eb',
          secondary: '#9aa4b2',
          muted: '#6b7280',
        },
        border: {
          soft: '#1f2737',
        },
      },
      boxShadow: {
        inset: 'inset 0 1px 0 0 rgba(255,255,255,0.05)',
        panel: '0 6px 30px rgba(0,0,0,0.35)',
      },
      keyframes: {
        caret: {
          '0%, 40%': { opacity: '1' },
          '60%, 100%': { opacity: '0' },
        },
      },
      animation: {
        caret: 'caret 1.2s infinite',
      },
    },
  },
  plugins: [],
};