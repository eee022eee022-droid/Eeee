/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Unbounded"', 'system-ui', 'sans-serif'],
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
      },
      colors: {
        cream: '#F7F1E8',
        sand: '#EBDFCF',
        clay: '#C68B6A',
        cocoa: '#4B2E1F',
        rose: '#E9B8A8',
        charcoal: '#1B1512',
      },
      boxShadow: {
        soft: '0 20px 50px -20px rgba(75, 46, 31, 0.25)',
      },
    },
  },
  plugins: [],
}
