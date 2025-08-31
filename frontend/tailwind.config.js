/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        'c-white': 'var(--c-white)',
        'c-pos': 'var(--c-pos)',
        'c-neg': 'var(--c-neg)',
        'c-a1': 'var(--c-a1)',
        'c-a2': 'var(--c-a2)',
        'c-a3': 'var(--c-a3)',
        'border': 'var(--border)',
        'text-strong': 'var(--text-strong)',
        'text-muted': 'var(--text-muted)',
        'text-subtle': 'var(--text-subtle)'
      }
    }
  },
  plugins: []
}
