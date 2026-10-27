/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        app: '#090b10',
        panel: '#0f131a',
        surface: {
          DEFAULT: '#161b24',
          hover: '#1e2430',
          active: '#262f3f',
        },
        subtle: '#1f2633',
        medium: '#2a3445',
        focus: '#38bdf8',
        brand: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'glow-blue': '0 0 15px -3px rgba(56, 189, 248, 0.25)',
        'glow-emerald': '0 0 15px -3px rgba(52, 211, 153, 0.25)',
        'studio-panel': '0 4px 20px -2px rgba(0, 0, 0, 0.5)',
      },
    },
  },
  plugins: [],
}
