/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0d1117', // Deepest background
          850: '#0c1219', // Alternative deep
          800: '#161b22', // Elevated panels
          750: '#1a1f26', // Card background
          700: '#21262d', // Borders, dividers
          650: '#282d35', // Hover states
          600: '#30363d', // Secondary backgrounds
          550: '#3a4149', // Tertiary backgrounds
          500: '#484f58', // Disabled states
        }
      },
      backgroundImage: {
        'dark-gradient': 'linear-gradient(180deg, #0d1117 0%, #161b22 100%)',
        'dark-gradient-subtle': 'linear-gradient(135deg, rgba(255,255,255,0.02) 0%, transparent 50%)',
        'dark-glow': 'radial-gradient(ellipse at top, rgba(35,134,182,0.08) 0%, transparent 60%)',
      }
    },
  },
  plugins: [],
}
